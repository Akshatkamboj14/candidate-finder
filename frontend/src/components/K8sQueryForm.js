import React, { useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Textarea,
  VStack,
  Heading,
  Text,
  Code,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  useToast,
  Spinner
} from "@chakra-ui/react";
import { k8sApi } from "../services/api";

export default function K8sQueryForm() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      toast({
        title: "Error",
        description: "Please enter a query",
        status: "error",
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      const result = await k8sApi.queryK8s(query);
      
      // Check if the response contains a security error
      if (result.error) {
        toast({
          title: "🔒 Security Warning",
          description: result.error,
          status: "error",
          duration: 8000,
          isClosable: true,
        });
        setResponse(result); // Still show the response for debugging
        return;
      }
      
      setResponse(result);
      toast({
        title: "Success",
        description: "Query processed successfully",
        status: "success",
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: error.message || "Failed to process query",
        status: "error",
        duration: 5000,
      });
      console.error("K8s query error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box maxW="4xl" mx="auto" p={6}>
      <Heading size="lg" mb={6} color="blue.600">
        🚢 Kubernetes Assistant
      </Heading>
      
      <Alert status="info" mb={4}>
        <AlertIcon />
        Ask questions about your Kubernetes cluster like "list all pods", "show logs for pod xyz", or "describe service my-app"
      </Alert>

      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch">
          <FormControl>
            <FormLabel>Your K8s Query</FormLabel>
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Examples:&#10;- list all pods&#10;- show logs for pod frontend-xyz&#10;- describe service backend&#10;- get deployments in namespace production"
              size="lg"
              rows={4}
              resize="vertical"
            />
          </FormControl>

          <Button
            type="submit"
            colorScheme="blue"
            size="lg"
            isLoading={isLoading}
            loadingText="Processing Query..."
            leftIcon={isLoading ? <Spinner size="sm" /> : undefined}
            disabled={!query.trim()}
          >
            Execute Query
          </Button>

          {response && (
            <Box mt={6}>
              <VStack spacing={4} align="stretch">
                {response.error && (
                  <Alert status="error">
                    <AlertIcon />
                    <Box>
                      <AlertTitle mr={2}>Security Warning!</AlertTitle>
                      <AlertDescription>
                        {response.error}
                        {response.suggestion && (
                          <Box mt={2}>
                            <Text fontSize="sm" fontStyle="italic">
                              💡 {response.suggestion}
                            </Text>
                          </Box>
                        )}
                      </AlertDescription>
                    </Box>
                  </Alert>
                )}

                {response.enhanced_response && (
                  <Box p={4} bg="green.50" borderRadius="md" border="1px solid" borderColor="green.200">
                    <Text fontWeight="bold" mb={2} color="green.800">
                      📋 AI Analysis:
                    </Text>
                    <Text color="green.700" whiteSpace="pre-wrap">
                      {response.enhanced_response}
                    </Text>
                  </Box>
                )}

                {response.parsed_intent && (
                  <Box p={4} bg="blue.50" borderRadius="md" border="1px solid" borderColor="blue.200">
                    <Text fontWeight="bold" mb={2} color="blue.800">
                      🎯 Parsed Intent:
                    </Text>
                    <Code display="block" p={2} bg="white" borderRadius="sm">
                      {JSON.stringify(response.parsed_intent, null, 2)}
                    </Code>
                  </Box>
                )}

                {response.raw_response && (
                  <Box p={4} bg="gray.50" borderRadius="md" border="1px solid" borderColor="gray.200">
                    <Text fontWeight="bold" mb={2} color="gray.800">
                      🖥️ Raw kubectl Output:
                    </Text>
                    <Code display="block" whiteSpace="pre" p={3} bg="black" color="green.300" borderRadius="sm" fontSize="sm">
                      {response.raw_response}
                    </Code>
                  </Box>
                )}
              </VStack>
            </Box>
          )}
        </VStack>
      </form>
    </Box>
  );
}
