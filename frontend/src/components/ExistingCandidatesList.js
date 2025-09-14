import React from 'react';
import {
  Box,
  Heading,
  Text,
  useToast,
  Spinner,
  VStack,
  Badge,
  Button,
  Flex,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
} from '@chakra-ui/react';
import { githubApi } from '../services/api';
import { CandidateList } from './CandidateList';
import { RepeatIcon, DeleteIcon } from '@chakra-ui/icons';

export const ExistingCandidatesList = () => {
  const [isLoading, setIsLoading] = React.useState(true);
  const [candidates, setCandidates] = React.useState(null);
  const [lastUpdated, setLastUpdated] = React.useState(null);
  const [isClearingDb, setIsClearingDb] = React.useState(false);
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const cancelRef = React.useRef();

  const fetchExistingCandidates = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await githubApi.inspectCollection();
      if (response.items) {
        setCandidates(response.items);
        setLastUpdated(new Date());
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error.message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  // Initial load
  React.useEffect(() => {
    fetchExistingCandidates();
  }, [fetchExistingCandidates]);

  if (isLoading) {
    return (
      <Box textAlign="center" py={10}>
        <Spinner size="xl" />
        <Text mt={4}>Loading candidates...</Text>
      </Box>
    );
  }

  if (!candidates || candidates.length === 0) {
    return (
      <Box textAlign="center" py={10}>
        <Text>No candidates found in the database.</Text>
      </Box>
    );
  }

  const handleClearDatabase = async () => {
    try {
      setIsClearingDb(true);
      await githubApi.clearDatabase();
      toast({
        title: "Database Cleared",
        description: "All candidates have been removed successfully.",
        status: "success",
        duration: 3000,
      });
      fetchExistingCandidates();
    } catch (error) {
      toast({
        title: "Error",
        description: error.message,
        status: "error",
        duration: 5000,
      });
    } finally {
      setIsClearingDb(false);
      onClose();
    }
  };

  return (
    <VStack spacing={6} width="100%">
      <Box width="100%">
        <Flex 
          justify="space-between" 
          align={{ base: "start", md: "center" }}
          mb={4}
          flexDirection={{ base: "column", md: "row" }}
          gap={4}
        >
          <Box>
            <Heading size="md">All Stored Candidates</Heading>
            <Text color="gray.600" mt={1}>
              Total candidates: {candidates.length}
              {lastUpdated && (
                <> • Last updated: {lastUpdated.toLocaleTimeString()}</>
              )}
            </Text>
          </Box>
          <Flex gap={2}>
            <Button
              leftIcon={<RepeatIcon />}
              onClick={fetchExistingCandidates}
              isLoading={isLoading}
              size="sm"
              colorScheme="blue"
            >
              Refresh
            </Button>
            <Button
              leftIcon={<DeleteIcon />}
              onClick={onOpen}
              isLoading={isClearingDb}
              size="sm"
              colorScheme="red"
            >
              Clear Database
            </Button>
          </Flex>
        </Flex>

        <AlertDialog
          isOpen={isOpen}
          leastDestructiveRef={cancelRef}
          onClose={onClose}
        >
          <AlertDialogOverlay>
            <AlertDialogContent>
              <AlertDialogHeader fontSize="lg" fontWeight="bold">
                Clear Database
              </AlertDialogHeader>

              <AlertDialogBody>
                Are you sure? This will permanently remove all candidates from the database.
                This action cannot be undone.
              </AlertDialogBody>

              <AlertDialogFooter>
                <Button ref={cancelRef} onClick={onClose}>
                  Cancel
                </Button>
                <Button colorScheme="red" onClick={handleClearDatabase} ml={3}>
                  Clear Database
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialogOverlay>
        </AlertDialog>

        {/* Stats row */}
        <Flex gap={4} mb={4}>
          <Badge colorScheme="blue" p={2}>
            Active Profiles: {candidates.length}
          </Badge>
          <Badge colorScheme="green" p={2}>
            With Repos: {candidates.filter(c => c.metadata?.repos_count > 0).length}
          </Badge>
          <Badge colorScheme="purple" p={2}>
            With Skills: {candidates.filter(c => c.metadata?.skills_list).length}
          </Badge>
        </Flex>

        <CandidateList candidates={candidates} />
      </Box>
    </VStack>
  );
};