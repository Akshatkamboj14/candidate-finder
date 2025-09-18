from typing import Dict, Any, TypedDict, List, Optional
import subprocess
import json
import re
import logging
from dataclasses import dataclass

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from ...infrastructure.aws.bedrock_embeddings import get_text_completion

logger = logging.getLogger(__name__)

@dataclass
class K8sIntent:
    """Structured representation of a K8s query intent"""
    resource_type: str
    action: str
    resource_name: Optional[str] = None
    namespace: Optional[str] = None
    additional_flags: List[str] = None
    
    def __post_init__(self):
        if self.additional_flags is None:
            self.additional_flags = []

class K8sState(TypedDict):
    """State for the K8s Assistant workflow"""
    query: str
    intent: Optional[K8sIntent]
    security_check_passed: bool
    kubectl_output: str
    enhanced_response: str
    error: Optional[str]
    suggestion: Optional[str]
    messages: List[Dict[str, Any]]

class K8sLangGraphAssistant:
    """
    LangGraph-based Kubernetes Assistant that processes natural language queries
    through a structured workflow with proper error handling and security checks.
    """
    
    def __init__(self):
        self.supported_resources = [
            "pods", "services", "deployments", "configmaps", 
            "ingress", "nodes", "namespaces", "persistentvolumes", "persistentvolumeclaims"
        ]
        self.supported_actions = ["list", "get", "describe", "logs"]
        self.banned_actions = ["delete", "edit", "patch", "apply", "create"]
        self.restricted_resources = ["secrets", "roles", "clusterroles"]
        
        # Initialize the LangGraph workflow
        self.workflow = self._create_workflow()
        
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for K8s query processing"""
        workflow = StateGraph(K8sState)
        
        # Add nodes to the workflow
        workflow.add_node("security_check", self._security_check_node)
        workflow.add_node("parse_intent", self._parse_intent_node)
        workflow.add_node("resolve_resources", self._resolve_resources_node)
        workflow.add_node("execute_kubectl", self._execute_kubectl_node)
        workflow.add_node("enhance_response", self._enhance_response_node)
        workflow.add_node("error_handler", self._error_handler_node)
        
        # Define the workflow edges
        workflow.set_entry_point("security_check")
        
        # Security check routing
        workflow.add_conditional_edges(
            "security_check",
            self._security_check_router,
            {
                "continue": "parse_intent",
                "error": "error_handler"
            }
        )
        
        # Parse intent routing
        workflow.add_conditional_edges(
            "parse_intent",
            self._parse_intent_router,
            {
                "continue": "resolve_resources",
                "error": "error_handler"
            }
        )
        
        # Continue through the workflow
        workflow.add_edge("resolve_resources", "execute_kubectl")
        workflow.add_edge("execute_kubectl", "enhance_response")
        workflow.add_edge("enhance_response", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a K8s query through the LangGraph workflow.
        
        Args:
            query: Natural language query about Kubernetes resources
            
        Returns:
            Dict containing processed results or error information
        """
        initial_state = K8sState(
            query=query,
            intent=None,
            security_check_passed=False,
            kubectl_output="",
            enhanced_response="",
            error=None,
            suggestion=None,
            messages=[]
        )
        
        try:
            # Run the workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Format the response
            return self._format_response(final_state)
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "query": query,
                "error": f"Internal error: {str(e)}",
                "suggestion": "Please try rephrasing your query or contact support.",
                "success": False
            }

    def _security_check_node(self, state: K8sState) -> K8sState:
        """Node: Perform security checks on the query"""
        query_lower = state["query"].lower()
        
        # Check for banned actions
        for banned_action in self.banned_actions:
            if banned_action in query_lower:
                state["error"] = f"🚫 Security Warning: '{banned_action}' operations are not allowed for safety reasons."
                state["suggestion"] = "You can only perform read-only operations like 'list', 'get', 'describe', and 'logs'."
                return state
        
        # Check for restricted resources
        for restricted in self.restricted_resources:
            if restricted in query_lower:
                state["error"] = f"🔒 Access Denied: '{restricted}' resources are restricted for security reasons."
                state["suggestion"] = "Try querying other resources like pods, services, deployments, configmaps, or ingress instead."
                return state
        
        state["security_check_passed"] = True
        return state

    def _security_check_router(self, state: K8sState) -> str:
        """Router: Determine next step after security check"""
        if state["error"]:
            return "error"
        return "continue"

    async def _parse_intent_node(self, state: K8sState) -> K8sState:
        """Node: Parse the natural language query into structured intent"""
        try:
            intent_data = await self._parse_with_llm(state["query"])
            
            # Validate the parsed intent
            validated_intent = self._validate_intent(intent_data)
            state["intent"] = K8sIntent(**validated_intent)
            
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            # Fallback to rule-based parsing
            try:
                fallback_intent = self._fallback_parse(state["query"])
                state["intent"] = K8sIntent(**fallback_intent)
            except Exception as fallback_error:
                logger.error(f"Fallback parsing also failed: {fallback_error}")
                state["error"] = "Failed to understand the query. Please try rephrasing."
                state["suggestion"] = "Use clear commands like 'list pods', 'show logs for pod-name', or 'describe service-name'."
        
        return state

    def _parse_intent_router(self, state: K8sState) -> str:
        """Router: Determine next step after intent parsing"""
        if state["error"]:
            return "error"
        return "continue"

    async def _resolve_resources_node(self, state: K8sState) -> K8sState:
        """Node: Resolve partial resource names to actual resource names"""
        if not state["intent"] or not state["intent"].resource_name:
            return state
        
        try:
            resolved_name = await self._resolve_resource_name(state["intent"])
            state["intent"].resource_name = resolved_name
        except Exception as e:
            logger.warning(f"Resource resolution failed: {e}")
            # Continue with original name
        
        return state

    def _execute_kubectl_node(self, state: K8sState) -> K8sState:
        """Node: Execute the kubectl command based on parsed intent"""
        try:
            intent = state["intent"]
            if not intent:
                raise ValueError("No intent available for kubectl execution")
            
            cmd = self._build_kubectl_command(intent)
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                state["kubectl_output"] = result.stdout.strip()
            else:
                error_msg = result.stderr.strip() or "Unknown kubectl error"
                state["error"] = f"kubectl error: {error_msg}"
                state["suggestion"] = "Check if the resource exists and you have proper permissions."
                
        except subprocess.TimeoutExpired:
            state["error"] = "kubectl command timed out"
            state["suggestion"] = "The cluster may be unresponsive. Try again later."
        except Exception as e:
            logger.error(f"kubectl execution failed: {e}")
            state["error"] = f"Command execution failed: {str(e)}"
            state["suggestion"] = "Please check your query syntax and try again."
        
        return state

    async def _enhance_response_node(self, state: K8sState) -> K8sState:
        """Node: Enhance the kubectl output with AI analysis"""
        if not state["kubectl_output"] or state["error"]:
            return state
        
        try:
            prompt = f"""
Analyze this Kubernetes output and provide a helpful summary for the user.

Original Query: "{state['query']}"
Kubectl Output: {state['kubectl_output']}

Provide a clear, concise analysis that:
1. Summarizes what was found
2. Highlights important information
3. Suggests next steps if appropriate
4. Explains any issues or concerns

Keep the response practical and user-friendly.
"""
            
            enhanced = await get_text_completion(prompt)
            state["enhanced_response"] = enhanced.strip()
            
        except Exception as e:
            logger.error(f"Response enhancement failed: {e}")
            # Continue without enhancement
            state["enhanced_response"] = "Raw kubectl output provided above."
        
        return state

    def _error_handler_node(self, state: K8sState) -> K8sState:
        """Node: Handle errors and provide helpful responses"""
        if not state["error"]:
            state["error"] = "An unknown error occurred"
            state["suggestion"] = "Please try rephrasing your query"
        
        # Log the error for debugging
        logger.error(f"K8s Assistant error for query '{state['query']}': {state['error']}")
        
        return state

    async def _parse_with_llm(self, query: str) -> Dict[str, Any]:
        """Parse query using LLM with structured prompting"""
        prompt = f"""
Parse this Kubernetes query into structured format:

Query: "{query}"

CRITICAL RULES:
1. resource_type must be one of: {', '.join(self.supported_resources)}
2. action must be one of: {', '.join(self.supported_actions)}
3. If query contains namespace names (kube-system, default, etc.), put them in namespace field
4. resource_name should be null unless a specific resource is mentioned

Return ONLY valid JSON:
{{
    "resource_type": "string",
    "action": "string",
    "resource_name": "string or null",
    "namespace": "string or null",
    "additional_flags": []
}}

Examples:
- "list pods" -> {{"resource_type": "pods", "action": "list", "resource_name": null, "namespace": null, "additional_flags": []}}
- "show logs for backend pod" -> {{"resource_type": "pods", "action": "logs", "resource_name": "backend", "namespace": null, "additional_flags": []}}
- "pods in kube-system" -> {{"resource_type": "pods", "action": "list", "resource_name": null, "namespace": "kube-system", "additional_flags": []}}
"""
        
        response = await get_text_completion(prompt)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError("No valid JSON found in LLM response")

    def _validate_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize parsed intent"""
        # Set defaults
        intent_data.setdefault("resource_type", "pods")
        intent_data.setdefault("action", "list")
        intent_data.setdefault("resource_name", None)
        intent_data.setdefault("namespace", None)
        intent_data.setdefault("additional_flags", [])
        
        # Security checks
        if intent_data["resource_type"] in self.restricted_resources:
            raise ValueError(f"Access denied to {intent_data['resource_type']}")
        
        if intent_data["action"] in self.banned_actions:
            raise ValueError(f"Action {intent_data['action']} is not allowed")
        
        # Resource mapping
        resource_map = {
            "pod": "pods", "svc": "services", "deploy": "deployments",
            "deployment": "deployments", "cm": "configmaps",
            "pv": "persistentvolumes", "pvc": "persistentvolumeclaims"
        }
        
        if intent_data["resource_type"] not in self.supported_resources:
            intent_data["resource_type"] = resource_map.get(
                intent_data["resource_type"], "pods"
            )
        
        return intent_data

    def _fallback_parse(self, query: str) -> Dict[str, Any]:
        """Fallback rule-based parsing when LLM fails"""
        query_lower = query.lower()
        
        # Determine action
        action = "list"
        if "logs" in query_lower:
            action = "logs"
        elif "describe" in query_lower:
            action = "describe"
        elif "get" in query_lower or "show" in query_lower:
            action = "get"
        
        # Determine resource type
        resource_type = "pods"
        if "service" in query_lower or "svc" in query_lower:
            resource_type = "services"
        elif "deployment" in query_lower or "deploy" in query_lower:
            resource_type = "deployments"
        elif "configmap" in query_lower or "cm" in query_lower:
            resource_type = "configmaps"
        elif "pv" in query_lower and "pvc" not in query_lower:
            resource_type = "persistentvolumes"
        elif "pvc" in query_lower:
            resource_type = "persistentvolumeclaims"
        
        return {
            "resource_type": resource_type,
            "action": action,
            "resource_name": None,
            "namespace": None,
            "additional_flags": []
        }

    async def _resolve_resource_name(self, intent: K8sIntent) -> str:
        """Resolve partial resource names to actual names"""
        if not intent.resource_name or len(intent.resource_name) > 20:
            return intent.resource_name
        
        try:
            cmd = ["kubectl", "get", intent.resource_type, "-o", "name"]
            if intent.namespace:
                cmd.extend(["-n", intent.namespace])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                resources = result.stdout.strip().split('\n')
                resources = [r.split('/')[-1] for r in resources if r]
                
                # Find best match
                for resource in resources:
                    if intent.resource_name.lower() in resource.lower():
                        return resource
            
            return intent.resource_name
            
        except Exception:
            return intent.resource_name

    def _build_kubectl_command(self, intent: K8sIntent) -> List[str]:
        """Build kubectl command from intent"""
        cmd = ["kubectl"]
        
        if intent.action == "logs":
            cmd.extend(["logs"])
            if intent.resource_name:
                cmd.append(intent.resource_name)
            else:
                raise ValueError("Resource name required for logs")
        
        elif intent.action in ["list", "get"]:
            cmd.extend(["get", intent.resource_type])
            if intent.resource_name:
                cmd.append(intent.resource_name)
        
        elif intent.action == "describe":
            cmd.extend(["describe", intent.resource_type])
            if intent.resource_name:
                cmd.append(intent.resource_name)
        
        # Add namespace
        if intent.namespace:
            cmd.extend(["-n", intent.namespace])
        
        # Add additional flags
        cmd.extend(intent.additional_flags)
        
        return cmd

    def _format_response(self, state: K8sState) -> Dict[str, Any]:
        """Format the final response"""
        if state["error"]:
            return {
                "query": state["query"],
                "error": state["error"],
                "suggestion": state["suggestion"],
                "success": False
            }
        
        return {
            "query": state["query"],
            "parsed_intent": state["intent"].__dict__ if state["intent"] else None,
            "raw_response": state["kubectl_output"],
            "enhanced_response": state["enhanced_response"],
            "success": True
        }
