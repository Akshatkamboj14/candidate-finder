from typing import Dict, Any, TypedDict, Annotated
import json
import re
import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from ...infrastructure.aws.bedrock_embeddings import get_text_completion

logger = logging.getLogger(__name__)

class K8sState(TypedDict):
    """State for the K8s Assistant workflow"""
    query: str
    parsed_intent: Dict[str, Any]
    security_check: Dict[str, Any]
    kubectl_result: str
    enhanced_response: str
    error: str
    messages: list

class K8sAssistant:
    """
    Kubernetes Assistant that processes natural language queries
    and translates them to kubectl commands with LLM enhancement.
    """
    
    def __init__(self):
        self.supported_resources = [
            "pods", "services", "deployments", "configmaps", 
            "ingress", "nodes", "namespaces", "persistentvolumes", "persistentvolumeclaims"
        ]
        self.supported_actions = [
            "list", "get", "describe", "logs"
        ]
        self.banned_actions = ["delete", "edit", "patch", "apply", "create"]
        self.restricted_resources = ["secrets"]
        
        # Initialize Kubernetes client
        try:
            # Try to load in-cluster config first (when running in a pod)
            config.load_incluster_config()
        except config.ConfigException:
            try:
                # Fall back to kubeconfig file
                config.load_kube_config()
            except config.ConfigException:
                logger.warning("Could not load Kubernetes config. Some features may not work.")
        
        # Initialize API clients
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for K8s query processing"""
        
        # Define the workflow graph
        workflow = StateGraph(K8sState)
        
        # Add nodes
        workflow.add_node("security_check", self._security_check_node)
        workflow.add_node("parse_intent", self._parse_intent_node)
        workflow.add_node("resolve_resources", self._resolve_resources_node)
        workflow.add_node("execute_kubectl", self._execute_kubectl_node)
        workflow.add_node("enhance_response", self._enhance_response_node)
        workflow.add_node("format_output", self._format_output_node)
        
        # Define the workflow edges
        workflow.set_entry_point("security_check")
        
        # Security check routing
        workflow.add_conditional_edges(
            "security_check",
            self._route_after_security,
            {
                "error": "format_output",
                "continue": "parse_intent"
            }
        )
        
        # Parse intent routing
        workflow.add_conditional_edges(
            "parse_intent",
            self._route_after_parsing,
            {
                "error": "format_output",
                "continue": "resolve_resources"
            }
        )
        
        # Continue workflow
        workflow.add_edge("resolve_resources", "execute_kubectl")
        workflow.add_edge("execute_kubectl", "enhance_response")
        workflow.add_edge("enhance_response", "format_output")
        workflow.add_edge("format_output", END)
        
        return workflow.compile()

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language Kubernetes query using LangGraph workflow.
        
        Args:
            query: Natural language query about Kubernetes resources
            
        Returns:
            Dict containing parsed intent, raw kubectl output, and enhanced response
        """
        try:
            # Initialize state
            initial_state: K8sState = {
                "query": query,
                "parsed_intent": {},
                "security_check": {},
                "kubectl_result": "",
                "enhanced_response": "",
                "error": "",
                "messages": [HumanMessage(content=query)]
            }
            
            # Execute the workflow
            result = await self.workflow.ainvoke(initial_state)
            
            # Return the final result
            return {
                "query": query,
                "parsed_intent": result.get("parsed_intent"),
                "raw_response": result.get("kubectl_result"),
                "enhanced_response": result.get("enhanced_response"),
                "error": result.get("error"),
                "success": not bool(result.get("error"))
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "query": query,
                "error": f"An unexpected error occurred: {str(e)}",
                "success": False
            }
            
        except Exception as e:
            logger.error(f"Error processing K8s query: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "success": False
            }

    # Original helper methods (used by LangGraph nodes)
    
    async def _resolve_resource_names(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently resolve partial resource names to actual resource names.
        Handles cases like 'frontend pod', 'backend service', etc.
        """
        if not intent.get("resource_name") or intent["resource_name"] in [None, ""]:
            return intent
        
        partial_name = intent["resource_name"].lower()
        resource_type = intent["resource_type"]
        namespace = intent.get("namespace", "default")
        
        # If it's already a full resource name (contains multiple hyphens), return as is
        if len(partial_name) > 20 and partial_name.count("-") >= 3:
            return intent
        
        try:
            # Get list of resources using Kubernetes client
            resource_names = []
            
            if resource_type == "pods":
                pods = self.v1.list_namespaced_pod(namespace=namespace)
                resource_names = [pod.metadata.name for pod in pods.items]
            elif resource_type == "services":
                services = self.v1.list_namespaced_service(namespace=namespace)
                resource_names = [svc.metadata.name for svc in services.items]
            elif resource_type == "deployments":
                deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
                resource_names = [dep.metadata.name for dep in deployments.items]
            elif resource_type == "configmaps":
                configmaps = self.v1.list_namespaced_config_map(namespace=namespace)
                resource_names = [cm.metadata.name for cm in configmaps.items]
            elif resource_type == "persistentvolumeclaims":
                pvcs = self.v1.list_namespaced_persistent_volume_claim(namespace=namespace)
                resource_names = [pvc.metadata.name for pvc in pvcs.items]
            elif resource_type == "nodes":
                nodes = self.v1.list_node()
                resource_names = [node.metadata.name for node in nodes.items]
            elif resource_type == "namespaces":
                namespaces = self.v1.list_namespace()
                resource_names = [ns.metadata.name for ns in namespaces.items]
            
            if resource_names:
                # Try different matching strategies
                matches = []
                
                # Strategy 1: Exact match
                for name in resource_names:
                    if name.lower() == partial_name:
                        intent["resource_name"] = name
                        return intent
                
                # Strategy 2: Starts with partial name
                for name in resource_names:
                    if name.lower().startswith(partial_name):
                        matches.append(name)
                
                # Strategy 3: Contains partial name
                if not matches:
                    for name in resource_names:
                        if partial_name in name.lower():
                            matches.append(name)
                
                # Strategy 4: Fuzzy matching for common patterns
                if not matches:
                    fuzzy_patterns = {
                        "frontend": ["front", "fe", "ui", "web"],
                        "backend": ["back", "be", "api", "server"],
                        "database": ["db", "postgres", "mysql", "mongo"],
                        "redis": ["cache", "session"],
                        "nginx": ["proxy", "lb", "loadbalancer"]
                    }
                    
                    for name in resource_names:
                        name_lower = name.lower()
                        for key, patterns in fuzzy_patterns.items():
                            if key == partial_name or partial_name in patterns:
                                if key in name_lower or any(p in name_lower for p in patterns):
                                    matches.append(name)
                                    break
                
                # Return best match
                if matches:
                    # Prefer shorter names (often more specific)
                    best_match = min(matches, key=len)
                    intent["resource_name"] = best_match
                    intent["resolved_from"] = partial_name
                    if len(matches) > 1:
                        intent["other_matches"] = matches[1:5]  # Show up to 4 other matches
                    return intent
                
                # If no good match found, return as is with a note
                intent["_resolution_note"] = f"No match found for '{partial_name}'. Available: {', '.join(resource_names[:5])}"
                
        except ApiException as e:
            intent["_resolution_note"] = f"API error while resolving resource names: {e.reason}"
        except Exception as e:
            intent["_resolution_note"] = f"Error resolving resource names: {str(e)}"
        
        return intent

    def _parse_intent(self, query: str) -> Dict[str, Any]:
        """
        Use LLM to parse the natural language query into structured intent.
        """
        prompt = f"""
Parse this Kubernetes query and extract the following information. Pay special attention to natural language patterns:

Query: "{query}"

CRITICAL PARSING RULES:
1. If the query says "pods in [something] namespace" or "pods in [something]", then [something] is the NAMESPACE, not the resource_name
2. resource_name should be null unless a specific pod/service name is mentioned
3. "kube-system", "default", "monitoring" etc. are always NAMESPACES
4. "show me pods in kube-system" means: action=list, resource_type=pods, namespace=kube-system, resource_name=null

Please identify:
1. resource_type: The Kubernetes resource type (pods, services, deployments, etc.)
2. action: The action to perform (list, get, describe, logs, etc.)
3. resource_name: Specific resource name ONLY if a particular resource is mentioned (null otherwise)
4. namespace: Namespace if mentioned (null for default)
5. additional_flags: Any additional kubectl flags or options

Respond with ONLY a valid JSON object with these keys:
{{
    "resource_type": "string",
    "action": "string", 
    "resource_name": "string or null",
    "namespace": "string or null",
    "additional_flags": ["array of strings"]
}}

Examples:
- "show me pods in kube-system namespace" -> {{"resource_type": "pods", "action": "list", "resource_name": null, "namespace": "kube-system", "additional_flags": []}}
- "pods in kube-system" -> {{"resource_type": "pods", "action": "list", "resource_name": null, "namespace": "kube-system", "additional_flags": []}}
- "list all pods" -> {{"resource_type": "pods", "action": "list", "resource_name": null, "namespace": null, "additional_flags": []}}
- "show logs for backend pod" -> {{"resource_type": "pods", "action": "logs", "resource_name": "backend", "namespace": null, "additional_flags": []}}
- "describe coredns pod in kube-system" -> {{"resource_type": "pods", "action": "describe", "resource_name": "coredns", "namespace": "kube-system", "additional_flags": []}}
- "list pv" -> {{"resource_type": "persistentvolumes", "action": "list", "resource_name": null, "namespace": null, "additional_flags": []}}
- "show pvc" -> {{"resource_type": "persistentvolumeclaims", "action": "list", "resource_name": null, "namespace": null, "additional_flags": []}}
- "show the logs for this pod - backend-deployment-f8dbcddb8-knvlc" -> {{"resource_type": "pods", "action": "logs", "resource_name": "backend-deployment-f8dbcddb8-knvlc", "namespace": null, "additional_flags": []}}
"""
        
        try:
            parsed_response = get_text_completion(prompt)
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', parsed_response, re.DOTALL)
            if json_match:
                parsed_json = json.loads(json_match.group())
                # Validate the parsed result
                return self._validate_intent(parsed_json)
            else:
                logger.warning("No JSON found in LLM response, using fallback parsing")
                return self._fallback_parse(query)
                
        except ValueError as e:
            # Security violations should return error response
            error_msg = str(e)
            if "Access Denied" in error_msg or "Security Warning" in error_msg:
                return {
                    "query": query,
                    "error": error_msg,
                    "suggestion": "Try querying other resources like pods, services, deployments, configmaps, or ingress instead.",
                    "success": False
                }
            else:
                logger.error(f"Validation error: {e}, using fallback")
                return self._fallback_parse(query)
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}, using fallback")
            return self._fallback_parse(query)

    def _validate_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize the parsed intent."""
        # Ensure required fields exist
        intent.setdefault("resource_type", "pods")
        intent.setdefault("action", "list")
        intent.setdefault("resource_name", None)
        intent.setdefault("namespace", None)
        intent.setdefault("additional_flags", [])
        
        # Security check: Block restricted resource types
        restricted_resource_types = ["secrets", "secret", "roles", "role", "clusterroles", "clusterrole"]
        if intent["resource_type"] in restricted_resource_types:
            raise ValueError(f"🔒 Access Denied: '{intent['resource_type']}' resources are restricted for security reasons.")
        
        # Security check: Block banned actions
        if intent["action"] in self.banned_actions:
            raise ValueError(f"🚫 Security Warning: '{intent['action']}' operations are not allowed for safety reasons.")
        
        # Sanitize resource type
        if intent["resource_type"] not in self.supported_resources:
            # Try to map common aliases
            resource_map = {
                "pod": "pods",
                "svc": "services", 
                "deploy": "deployments",
                "deployment": "deployments",
                "cm": "configmaps",
                "pv": "persistentvolumes",
                "persistentvolume": "persistentvolumes",
                "pvc": "persistentvolumeclaims",
                "persistentvolumeclaim": "persistentvolumeclaims"
            }
            intent["resource_type"] = resource_map.get(intent["resource_type"], "pods")
        
        return intent

    def _fallback_parse(self, query: str) -> Dict[str, Any]:
        """
        Fallback parsing using simple keyword matching if LLM fails.
        Enhanced to handle natural language patterns.
        """
        query_lower = query.lower()
        
        # Extract action with better natural language understanding
        action = "list"
        if any(word in query_lower for word in ["logs", "log"]):
            action = "logs"
        elif any(word in query_lower for word in ["describe", "desc", "details"]):
            action = "describe"
        elif any(word in query_lower for word in ["get", "show", "find"]):
            if "logs" not in query_lower:
                action = "get"
            else:
                action = "logs"
        elif "delete" in query_lower:
            action = "delete"  # Will be caught by security check
        
        # Extract resource type with better matching
        resource_type = "pods"
        resource_patterns = {
            "pods": ["pod", "pods"],
            "services": ["service", "services", "svc"],
            "deployments": ["deployment", "deployments", "deploy"],
            "configmaps": ["configmap", "configmaps", "cm"],
            "ingress": ["ingress", "ing"],
            "nodes": ["node", "nodes"],
            "namespaces": ["namespace", "namespaces", "ns"],
            "persistentvolumes": ["persistentvolume", "persistentvolumes", "pv"],
            "persistentvolumeclaims": ["persistentvolumeclaim", "persistentvolumeclaims", "pvc"]
        }
        
        for resource, patterns in resource_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                resource_type = resource
                break
        
        # Extract namespace FIRST (before resource name)
        namespace = None
        common_namespaces = ["kube-system", "default", "monitoring", "ingress-nginx", "cert-manager", "kube-public"]
        
        # Check for "pods in [namespace]" pattern specifically
        if " in " in query_lower:
            # Pattern: "pods in kube-system" or "show me pods in kube-system namespace"
            for ns in common_namespaces:
                if f" in {ns}" in query_lower or f"in {ns}" in query_lower:
                    namespace = ns
                    break
        
        # Check for common namespace patterns
        if not namespace:
            for ns in common_namespaces:
                if ns in query_lower:
                    # Make sure it's not part of a resource name
                    if f" {ns} " in query_lower or query_lower.endswith(ns) or query_lower.startswith(ns):
                        namespace = ns
                        break
        
        # Check for explicit namespace patterns with regex
        if not namespace:
            namespace_patterns = [
                r"in\s+(\w+)\s+namespace",
                r"namespace\s+(\w+)",
                r"in\s+namespace\s+(\w+)",
                r"pods\s+in\s+(\w+)",
                r"in\s+(\w+-\w+)",  # For namespaces like kube-system
            ]
            
            import re
            for pattern in namespace_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    namespace = match.group(1)
                    break
        
        # Enhanced resource name extraction (after namespace removal)
        resource_name = None
        words = query.split()
        
        # For "pods in [namespace]" queries, resource_name should be null
        if namespace and f" in {namespace}" in query_lower:
            resource_name = None
        else:
            # Pattern: "show logs for backend pod"
            for i, word in enumerate(words):
                if word.lower() in ["for", "of"] and i + 1 < len(words):
                    next_word = words[i + 1]
                    # Skip if it's a namespace
                    if next_word.lower() not in common_namespaces:
                        if i + 2 < len(words) and words[i + 2].lower() in ["pod", "service", "deployment"]:
                            resource_name = next_word
                            break
            
            # Pattern: "backend pod" or "frontend-deployment-xyz"
            if not resource_name:
                for i, word in enumerate(words):
                    if word.lower() in ["pod", "service", "deployment"] and i > 0:
                        candidate = words[i - 1]
                        # Skip if it's a namespace or common words
                        if (candidate.lower() not in common_namespaces and 
                            candidate.lower() not in ["the", "a", "an", "all", "me", "show"]):
                            resource_name = candidate
                            break
                    elif "-" in word and len(word) > 10:  # Likely a k8s resource name
                        if word.lower() not in common_namespaces:
                            resource_name = word
                            break
            
            # Pattern: "pod name for frontend"
            if "name for" in query_lower and not resource_name:
                for i, word in enumerate(words):
                    if word.lower() == "for" and i + 1 < len(words):
                        candidate = words[i + 1]
                        if candidate.lower() not in common_namespaces:
                            resource_name = candidate
                            break
        
        return {
            "resource_type": resource_type,
            "action": action,
            "resource_name": resource_name,
            "namespace": namespace,
            "additional_flags": []
        }

    def _execute_kubectl(self, intent: Dict[str, Any]) -> str:
        """
        Execute the appropriate Kubernetes API call based on parsed intent.
        """
        try:
            action = intent["action"]
            resource_type = intent["resource_type"]
            resource_name = intent.get("resource_name")
            namespace = intent.get("namespace", "default")
            
            if action == "logs":
                if not resource_name:
                    return "Error: Resource name required for logs command"
                if resource_type != "pods":
                    return "Error: Logs can only be retrieved for pods"
                
                try:
                    logs = self.v1.read_namespaced_pod_log(
                        name=resource_name, 
                        namespace=namespace,
                        tail_lines=100  # Limit to last 100 lines
                    )
                    return logs
                except ApiException as e:
                    return f"Error retrieving logs: {e.reason}"
            
            elif action in ["list", "get"]:
                if resource_type == "pods":
                    if resource_name:
                        try:
                            pod = self.v1.read_namespaced_pod(name=resource_name, namespace=namespace)
                            return self._format_pod_details(pod)
                        except ApiException as e:
                            return f"Error getting pod: {e.reason}"
                    else:
                        try:
                            pods = self.v1.list_namespaced_pod(namespace=namespace)
                            return self._format_pods_list(pods.items)
                        except ApiException as e:
                            return f"Error listing pods: {e.reason}"
                
                elif resource_type == "services":
                    if resource_name:
                        try:
                            service = self.v1.read_namespaced_service(name=resource_name, namespace=namespace)
                            return self._format_service_details(service)
                        except ApiException as e:
                            return f"Error getting service: {e.reason}"
                    else:
                        try:
                            services = self.v1.list_namespaced_service(namespace=namespace)
                            return self._format_services_list(services.items)
                        except ApiException as e:
                            return f"Error listing services: {e.reason}"
                
                elif resource_type == "deployments":
                    if resource_name:
                        try:
                            deployment = self.apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)
                            return self._format_deployment_details(deployment)
                        except ApiException as e:
                            return f"Error getting deployment: {e.reason}"
                    else:
                        try:
                            deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
                            return self._format_deployments_list(deployments.items)
                        except ApiException as e:
                            return f"Error listing deployments: {e.reason}"
                
                elif resource_type == "nodes":
                    if resource_name:
                        try:
                            node = self.v1.read_node(name=resource_name)
                            return self._format_node_details(node)
                        except ApiException as e:
                            return f"Error getting node: {e.reason}"
                    else:
                        try:
                            nodes = self.v1.list_node()
                            return self._format_nodes_list(nodes.items)
                        except ApiException as e:
                            return f"Error listing nodes: {e.reason}"
                
                elif resource_type == "namespaces":
                    if resource_name:
                        try:
                            namespace_obj = self.v1.read_namespace(name=resource_name)
                            return self._format_namespace_details(namespace_obj)
                        except ApiException as e:
                            return f"Error getting namespace: {e.reason}"
                    else:
                        try:
                            namespaces = self.v1.list_namespace()
                            return self._format_namespaces_list(namespaces.items)
                        except ApiException as e:
                            return f"Error listing namespaces: {e.reason}"
                
                else:
                    return f"Error: Resource type '{resource_type}' not yet supported"
            
            elif action == "describe":
                # For describe, we'll provide detailed information
                if resource_type == "pods" and resource_name:
                    try:
                        pod = self.v1.read_namespaced_pod(name=resource_name, namespace=namespace)
                        return self._format_pod_describe(pod)
                    except ApiException as e:
                        return f"Error describing pod: {e.reason}"
                elif resource_type == "services" and resource_name:
                    try:
                        service = self.v1.read_namespaced_service(name=resource_name, namespace=namespace)
                        return self._format_service_describe(service)
                    except ApiException as e:
                        return f"Error describing service: {e.reason}"
                elif resource_type == "deployments" and resource_name:
                    try:
                        deployment = self.apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)
                        return self._format_deployment_describe(deployment)
                    except ApiException as e:
                        return f"Error describing deployment: {e.reason}"
                else:
                    return f"Error: Describe requires a specific resource name"
            
            else:
                return f"Error: Action '{action}' not supported"
                
        except Exception as e:
            return f"Error executing Kubernetes operation: {str(e)}"

    def _enhance_response(self, kubectl_output: str, intent: Dict[str, Any], original_query: str) -> str:
        """
        Use LLM to provide a human-friendly explanation of the kubectl output.
        """
        if not kubectl_output or kubectl_output.startswith("Error:"):
            return f"Unable to execute the query. {kubectl_output}"
        
        prompt = f"""
You are a Kubernetes expert assistant. A user asked: "{original_query}"

The system parsed this as wanting to {intent["action"]} {intent["resource_type"]} and executed a kubectl command.

Here's the kubectl output:
```
{kubectl_output}
```

Please provide a clear, human-friendly explanation of this output. Include:
1. A summary of what was found/shown
2. Any important observations about the status or health
3. Potential issues or recommendations if any
4. Next steps the user might want to take

Keep the response concise but informative. Use emojis sparingly for readability.
"""
        
        try:
            enhanced = get_text_completion(prompt)
            return enhanced.strip()
        except Exception as e:
            logger.error(f"Failed to enhance response: {e}")
            return f"Here's the kubectl output for your query:\n\n{kubectl_output}"
    
    # LangGraph Node Methods
    
    def _security_check_node(self, state: K8sState) -> K8sState:
        """Security check node - validates query for banned operations and restricted resources"""
        query_lower = state["query"].lower()
        
        # Check for banned actions
        for banned_action in self.banned_actions:
            if banned_action in query_lower:
                state["error"] = f"🚫 Security Warning: '{banned_action}' operations are not allowed for safety reasons."
                state["security_check"] = {"blocked": True, "reason": f"banned_action: {banned_action}"}
                return state
        
        # Check for restricted resources (with variations)
        restricted_patterns = {
            "secrets": ["secret", "secrets"],
            "roles": ["role", "roles", "rolebinding", "rolebindings"],
            "clusterroles": ["clusterrole", "clusterroles", "clusterrolebinding", "clusterrolebindings"]
        }
        
        for resource_type, patterns in restricted_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    state["error"] = f"🔒 Access Denied: '{pattern}' resources are restricted for security reasons."
                    state["security_check"] = {"blocked": True, "reason": f"restricted_resource: {pattern}"}
                    return state
        
        state["security_check"] = {"blocked": False}
        logger.info("Security check passed")
        return state
    
    def _parse_intent_node(self, state: K8sState) -> K8sState:
        """Parse intent node - converts natural language to structured intent"""
        try:
            intent = self._parse_intent(state["query"])
            
            # Check if parsing returned an error
            if isinstance(intent, dict) and intent.get("error"):
                state["error"] = intent["error"]
                return state
            
            state["parsed_intent"] = intent
            logger.info(f"Intent parsed: {intent}")
            return state
            
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            state["error"] = f"Failed to parse query: {str(e)}"
            return state
    
    async def _resolve_resources_node(self, state: K8sState) -> K8sState:
        """Resolve resources node - resolves partial resource names to actual names"""
        try:
            resolved_intent = await self._resolve_resource_names(state["parsed_intent"])
            state["parsed_intent"] = resolved_intent
            logger.info(f"Resources resolved: {resolved_intent}")
            return state
            
        except Exception as e:
            logger.error(f"Resource resolution failed: {e}")
            state["error"] = f"Failed to resolve resources: {str(e)}"
            return state
    
    def _execute_kubectl_node(self, state: K8sState) -> K8sState:
        """Execute kubectl node - runs the kubectl command"""
        try:
            kubectl_result = self._execute_kubectl(state["parsed_intent"])
            state["kubectl_result"] = kubectl_result
            logger.info(f"Kubectl executed, result length: {len(kubectl_result)}")
            return state
            
        except Exception as e:
            logger.error(f"Kubectl execution failed: {e}")
            state["error"] = f"Failed to execute kubectl: {str(e)}"
            return state
    
    def _enhance_response_node(self, state: K8sState) -> K8sState:
        """Enhance response node - uses LLM to enhance the kubectl output"""
        try:
            enhanced_response = self._enhance_response(
                state["kubectl_result"], 
                state["parsed_intent"], 
                state["query"]
            )
            state["enhanced_response"] = enhanced_response
            logger.info("Response enhanced by LLM")
            return state
            
        except Exception as e:
            logger.error(f"Response enhancement failed: {e}")
            # Don't fail the workflow if enhancement fails
            state["enhanced_response"] = "Enhancement unavailable"
            return state
    
    def _format_output_node(self, state: K8sState) -> K8sState:
        """Format output node - final formatting of the response"""
        # This node just passes through the state for final processing
        logger.info("Output formatted and ready")
        return state
    
    # Formatting helper methods for Kubernetes resources
    
    def _format_pods_list(self, pods):
        """Format a list of pods for display"""
        if not pods:
            return "No pods found"
        
        result = "NAME\t\tREADY\tSTATUS\t\tRESTARTS\tAGE\n"
        for pod in pods:
            ready_containers = sum(1 for condition in pod.status.conditions or [] 
                                 if condition.type == "Ready" and condition.status == "True")
            total_containers = len(pod.spec.containers)
            ready_status = f"{ready_containers}/{total_containers}"
            
            status = pod.status.phase
            restarts = sum(container_status.restart_count for container_status in pod.status.container_statuses or [])
            
            # Calculate age
            created = pod.metadata.creation_timestamp
            age = self._calculate_age(created)
            
            result += f"{pod.metadata.name}\t{ready_status}\t{status}\t\t{restarts}\t\t{age}\n"
        
        return result
    
    def _format_pod_details(self, pod):
        """Format detailed pod information"""
        result = f"Name: {pod.metadata.name}\n"
        result += f"Namespace: {pod.metadata.namespace}\n"
        result += f"Status: {pod.status.phase}\n"
        result += f"IP: {pod.status.pod_ip or 'N/A'}\n"
        result += f"Node: {pod.spec.node_name or 'N/A'}\n"
        result += f"Created: {pod.metadata.creation_timestamp}\n"
        
        if pod.spec.containers:
            result += "Containers:\n"
            for container in pod.spec.containers:
                result += f"  - {container.name}: {container.image}\n"
        
        return result
    
    def _format_pod_describe(self, pod):
        """Format detailed pod description similar to kubectl describe"""
        result = f"Name:         {pod.metadata.name}\n"
        result += f"Namespace:    {pod.metadata.namespace}\n"
        result += f"Priority:     {pod.spec.priority or 0}\n"
        result += f"Node:         {pod.spec.node_name or 'N/A'}\n"
        result += f"Start Time:   {pod.metadata.creation_timestamp}\n"
        
        if pod.metadata.labels:
            result += "Labels:       "
            result += "\n              ".join([f"{k}={v}" for k, v in pod.metadata.labels.items()])
            result += "\n"
        
        result += f"Status:       {pod.status.phase}\n"
        result += f"IP:           {pod.status.pod_ip or 'N/A'}\n"
        
        if pod.spec.containers:
            result += "Containers:\n"
            for container in pod.spec.containers:
                result += f"  {container.name}:\n"
                result += f"    Image:      {container.image}\n"
                result += f"    Port:       {container.ports[0].container_port if container.ports else 'N/A'}\n"
        
        return result
    
    def _format_services_list(self, services):
        """Format a list of services for display"""
        if not services:
            return "No services found"
        
        result = "NAME\t\tTYPE\t\tCLUSTER-IP\tEXTERNAL-IP\tPORT(S)\t\tAGE\n"
        for service in services:
            external_ip = service.status.load_balancer.ingress[0].ip if (
                service.status.load_balancer and 
                service.status.load_balancer.ingress
            ) else "<none>"
            
            ports = ",".join([f"{port.port}:{port.target_port}/{port.protocol}" 
                            for port in service.spec.ports or []])
            
            age = self._calculate_age(service.metadata.creation_timestamp)
            
            result += f"{service.metadata.name}\t{service.spec.type}\t{service.spec.cluster_ip}\t{external_ip}\t{ports}\t{age}\n"
        
        return result
    
    def _format_service_details(self, service):
        """Format detailed service information"""
        result = f"Name: {service.metadata.name}\n"
        result += f"Namespace: {service.metadata.namespace}\n"
        result += f"Type: {service.spec.type}\n"
        result += f"Cluster IP: {service.spec.cluster_ip}\n"
        
        if service.spec.ports:
            result += "Ports:\n"
            for port in service.spec.ports:
                result += f"  - {port.port}:{port.target_port}/{port.protocol}\n"
        
        return result
    
    def _format_service_describe(self, service):
        """Format detailed service description"""
        result = f"Name:              {service.metadata.name}\n"
        result += f"Namespace:         {service.metadata.namespace}\n"
        
        if service.metadata.labels:
            result += "Labels:            "
            result += "\n                   ".join([f"{k}={v}" for k, v in service.metadata.labels.items()])
            result += "\n"
        
        result += f"Type:              {service.spec.type}\n"
        result += f"IP Family Policy:  {service.spec.ip_family_policy or 'SingleStack'}\n"
        result += f"IP Families:       {','.join(service.spec.ip_families or ['IPv4'])}\n"
        result += f"IP:                {service.spec.cluster_ip}\n"
        
        if service.spec.ports:
            result += "Port:              "
            for i, port in enumerate(service.spec.ports):
                if i > 0:
                    result += "                   "
                result += f"{port.port}/{port.protocol} TargetPort: {port.target_port}\n"
        
        return result
    
    def _format_deployments_list(self, deployments):
        """Format a list of deployments for display"""
        if not deployments:
            return "No deployments found"
        
        result = "NAME\t\tREADY\tUP-TO-DATE\tAVAILABLE\tAGE\n"
        for deployment in deployments:
            ready = f"{deployment.status.ready_replicas or 0}/{deployment.spec.replicas or 0}"
            up_to_date = deployment.status.updated_replicas or 0
            available = deployment.status.available_replicas or 0
            age = self._calculate_age(deployment.metadata.creation_timestamp)
            
            result += f"{deployment.metadata.name}\t{ready}\t{up_to_date}\t\t{available}\t\t{age}\n"
        
        return result
    
    def _format_deployment_details(self, deployment):
        """Format detailed deployment information"""
        result = f"Name: {deployment.metadata.name}\n"
        result += f"Namespace: {deployment.metadata.namespace}\n"
        result += f"Replicas: {deployment.status.ready_replicas or 0}/{deployment.spec.replicas or 0}\n"
        result += f"Strategy: {deployment.spec.strategy.type}\n"
        result += f"Created: {deployment.metadata.creation_timestamp}\n"
        
        return result
    
    def _format_deployment_describe(self, deployment):
        """Format detailed deployment description"""
        result = f"Name:                   {deployment.metadata.name}\n"
        result += f"Namespace:              {deployment.metadata.namespace}\n"
        result += f"CreationTimestamp:      {deployment.metadata.creation_timestamp}\n"
        
        if deployment.metadata.labels:
            result += "Labels:                 "
            result += "\n                        ".join([f"{k}={v}" for k, v in deployment.metadata.labels.items()])
            result += "\n"
        
        result += f"Replicas:               {deployment.spec.replicas} desired | {deployment.status.updated_replicas or 0} updated | {deployment.status.replicas or 0} total | {deployment.status.available_replicas or 0} available | {deployment.status.unavailable_replicas or 0} unavailable\n"
        result += f"StrategyType:           {deployment.spec.strategy.type}\n"
        
        return result
    
    def _format_nodes_list(self, nodes):
        """Format a list of nodes for display"""
        if not nodes:
            return "No nodes found"
        
        result = "NAME\t\tSTATUS\tROLES\t\tAGE\tVERSION\n"
        for node in nodes:
            status = "Ready" if any(condition.type == "Ready" and condition.status == "True" 
                                  for condition in node.status.conditions or []) else "NotReady"
            
            roles = []
            if node.metadata.labels:
                for key in node.metadata.labels:
                    if key.startswith("node-role.kubernetes.io/"):
                        roles.append(key.split("/")[1])
            roles_str = ",".join(roles) if roles else "<none>"
            
            age = self._calculate_age(node.metadata.creation_timestamp)
            version = node.status.node_info.kubelet_version
            
            result += f"{node.metadata.name}\t{status}\t{roles_str}\t\t{age}\t{version}\n"
        
        return result
    
    def _format_node_details(self, node):
        """Format detailed node information"""
        result = f"Name: {node.metadata.name}\n"
        result += f"Roles: {','.join([key.split('/')[1] for key in node.metadata.labels.keys() if key.startswith('node-role.kubernetes.io/')])}\n"
        result += f"Labels: {len(node.metadata.labels or {})} labels\n"
        result += f"Kernel Version: {node.status.node_info.kernel_version}\n"
        result += f"OS Image: {node.status.node_info.os_image}\n"
        result += f"Container Runtime: {node.status.node_info.container_runtime_version}\n"
        result += f"Kubelet Version: {node.status.node_info.kubelet_version}\n"
        
        return result
    
    def _format_namespaces_list(self, namespaces):
        """Format a list of namespaces for display"""
        if not namespaces:
            return "No namespaces found"
        
        result = "NAME\t\t\tSTATUS\tAGE\n"
        for namespace in namespaces:
            status = namespace.status.phase
            age = self._calculate_age(namespace.metadata.creation_timestamp)
            
            result += f"{namespace.metadata.name}\t\t{status}\t{age}\n"
        
        return result
    
    def _format_namespace_details(self, namespace):
        """Format detailed namespace information"""
        result = f"Name: {namespace.metadata.name}\n"
        result += f"Status: {namespace.status.phase}\n"
        result += f"Created: {namespace.metadata.creation_timestamp}\n"
        
        if namespace.metadata.labels:
            result += f"Labels: {len(namespace.metadata.labels)} labels\n"
        
        return result
    
    def _calculate_age(self, creation_timestamp):
        """Calculate age from creation timestamp"""
        import datetime
        if not creation_timestamp:
            return "Unknown"
        
        now = datetime.datetime.now(datetime.timezone.utc)
        if creation_timestamp.tzinfo is None:
            creation_timestamp = creation_timestamp.replace(tzinfo=datetime.timezone.utc)
        
        age = now - creation_timestamp
        
        if age.days > 0:
            return f"{age.days}d"
        elif age.seconds > 3600:
            return f"{age.seconds // 3600}h"
        elif age.seconds > 60:
            return f"{age.seconds // 60}m"
        else:
            return f"{age.seconds}s"
