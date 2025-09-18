from typing import Dict, Any
import subprocess
import json
import re
import logging
from ...infrastructure.aws.bedrock_embeddings import get_text_completion

logger = logging.getLogger(__name__)

class K8sAssistant:
    """
    Kubernetes Assistant that processes natural language queries
    and translates them to kubectl commands with LLM enhancement.
    """
    
    def __init__(self):
        self.supported_resources = [
            "pods", "services", "deployments", "configmaps", 
            "ingress", "nodes", "namespaces", "persistentvolumes", "pvc"
        ]
        self.supported_actions = [
            "list", "get", "describe", "logs"
        ]
        self.banned_actions = ["delete", "edit", "patch", "apply", "create"]
        self.restricted_resources = ["secrets"]

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Main entry point for processing K8s queries.
        
        Args:
            query: Natural language query about K8s resources
            
        Returns:
            Dict containing parsed intent, raw kubectl output, and enhanced response
        """
        try:
            # Step 1: Check for banned operations or restricted resources
            security_check = self._security_check(query)
            if security_check:
                return security_check
            
            # Step 2: Parse the query intent using LLM
            intent = await self._parse_intent(query)
            logger.info(f"Parsed intent: {intent}")
            
            # Check if parsing returned a security error
            if isinstance(intent, dict) and intent.get("error"):
                return intent
            
            # Step 3: Resolve resource names if needed (e.g., "backend pod" -> actual pod name)
            resolved_intent = await self._resolve_resource_names(intent)
            logger.info(f"Resolved intent: {resolved_intent}")
            
            # Step 4: Execute kubectl command based on intent
            kubectl_result = self._execute_kubectl(resolved_intent)
            logger.info(f"Kubectl executed, result length: {len(kubectl_result)}")
            
            # Step 5: Enhance the response using LLM
            enhanced_response = await self._enhance_response(kubectl_result, resolved_intent, query)
            
            return {
                "query": query,
                "parsed_intent": resolved_intent,
                "raw_response": kubectl_result,
                "enhanced_response": enhanced_response,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error processing K8s query: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "success": False
            }

    def _security_check(self, query: str) -> Dict[str, Any]:
        """
        Check for banned operations and restricted resources.
        Returns error response if query is not allowed, None if safe.
        """
        query_lower = query.lower()
        
        # Check for banned actions
        for banned_action in self.banned_actions:
            if banned_action in query_lower:
                return {
                    "query": query,
                    "error": f"🚫 Security Warning: '{banned_action}' operations are not allowed for safety reasons.",
                    "suggestion": "You can only perform read-only operations like 'list', 'get', 'describe', and 'logs'.",
                    "success": False
                }
        
        # Check for restricted resources (with variations)
        restricted_patterns = {
            "secrets": ["secret", "secrets"],
            "roles": ["role", "roles", "rolebinding", "rolebindings"],
            "clusterroles": ["clusterrole", "clusterroles", "clusterrolebinding", "clusterrolebindings"]
        }
        
        for resource_type, patterns in restricted_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return {
                        "query": query,
                        "error": f"🔒 Access Denied: '{pattern}' resources are restricted for security reasons.",
                        "suggestion": "Try querying other resources like pods, services, deployments, configmaps, or ingress instead.",
                        "success": False
                    }
        
        # Also check the legacy way for backward compatibility
        for restricted in self.restricted_resources:
            if restricted in query_lower:
                return {
                    "query": query,
                    "error": f"🔒 Access Denied: '{restricted}' resources are restricted for security reasons.",
                    "suggestion": "Try querying other resources like pods, services, deployments, configmaps, or ingress instead.",
                    "success": False
                }
        
        return None

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
            # Get list of resources
            cmd = ["kubectl", "get", resource_type]
            if namespace and namespace != "default":
                cmd.extend(["-n", namespace])
            cmd.extend(["--no-headers", "-o", "custom-columns=NAME:.metadata.name"])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                resource_names = [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
                
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
                
        except subprocess.TimeoutExpired:
            intent["_resolution_note"] = "Timeout while resolving resource names"
        except Exception as e:
            intent["_resolution_note"] = f"Error resolving resource names: {str(e)}"
        
        return intent

    async def _parse_intent(self, query: str) -> Dict[str, Any]:
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
- "show the logs for this pod - backend-deployment-f8dbcddb8-knvlc" -> {{"resource_type": "pods", "action": "logs", "resource_name": "backend-deployment-f8dbcddb8-knvlc", "namespace": null, "additional_flags": []}}
"""
        
        try:
            parsed_response = await get_text_completion(prompt)
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
                "pv": "persistentvolumes"
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
            "namespaces": ["namespace", "namespaces", "ns"]
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
        Execute the appropriate kubectl command based on parsed intent.
        """
        try:
            cmd = ["kubectl"]
            
            # Build the command based on action
            if intent["action"] == "logs":
                cmd.extend(["logs"])
                if intent["resource_name"]:
                    cmd.append(intent["resource_name"])
                else:
                    return "Error: Resource name required for logs command"
            
            elif intent["action"] in ["list", "get"]:
                cmd.extend(["get", intent["resource_type"]])
                if intent["resource_name"]:
                    cmd.append(intent["resource_name"])
            
            elif intent["action"] == "describe":
                cmd.extend(["describe", intent["resource_type"]])
                if intent["resource_name"]:
                    cmd.append(intent["resource_name"])
            
            else:
                cmd.extend([intent["action"], intent["resource_type"]])
                if intent["resource_name"]:
                    cmd.append(intent["resource_name"])
            
            # Add namespace if specified
            if intent["namespace"]:
                cmd.extend(["-n", intent["namespace"]])
            
            # Add additional flags
            if intent["additional_flags"]:
                cmd.extend(intent["additional_flags"])
            
            # Execute the command
            logger.info(f"Executing command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                check=False
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return f"kubectl command failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return "Error: kubectl command timed out after 30 seconds"
        except FileNotFoundError:
            return "Error: kubectl command not found. Please ensure kubectl is installed and in PATH"
        except Exception as e:
            return f"Error executing kubectl: {str(e)}"

    async def _enhance_response(self, kubectl_output: str, intent: Dict[str, Any], original_query: str) -> str:
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
            enhanced = await get_text_completion(prompt)
            return enhanced.strip()
        except Exception as e:
            logger.error(f"Failed to enhance response: {e}")
            return f"Here's the kubectl output for your query:\n\n{kubectl_output}"
