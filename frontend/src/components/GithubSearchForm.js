import React from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  NumberInput,
  NumberInputField,
  VStack,
  useToast,
  Text,
} from '@chakra-ui/react';
import { githubApi } from '../services/api';

export const GithubSearchForm = ({ onSearchStarted, onCandidatesFound }) => {
  const [formData, setFormData] = React.useState({
    language: '',
    location: '',
    minFollowers: '',
    minRepos: '',
    maxUsers: 30,
    perUserRepos: 3
  });
  const [isLoading, setIsLoading] = React.useState(false);
  const [jobId, setJobId] = React.useState(null);
  const toast = useToast();
  
  // Poll job status
  React.useEffect(() => {
    let intervalId;
    if (jobId) {
      intervalId = setInterval(async () => {
        try {
          const status = await githubApi.getJobStatus(jobId);
          if (status.status === 'done') {
            clearInterval(intervalId);
            setJobId(null);
            setIsLoading(false);
            // Get the collection data
            const collection = await githubApi.inspectCollection();
            if (collection.items) {
              onCandidatesFound(collection.items);
            }
          } else if (status.status === 'failed') {
            clearInterval(intervalId);
            setJobId(null);
            setIsLoading(false);
            toast({
              title: 'Error',
              description: status.error || 'Failed to fetch candidates',
              status: 'error',
              duration: 5000,
            });
          }
        } catch (error) {
          clearInterval(intervalId);
          setJobId(null);
          setIsLoading(false);
          toast({
            title: 'Error',
            description: error.message,
            status: 'error',
            duration: 5000,
          });
        }
      }, 2000);
    }
    return () => intervalId && clearInterval(intervalId);
  }, [jobId, toast, onCandidatesFound]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    setIsLoading(true);
    try {
      // Convert empty strings to null for the backend
      const payload = {
        language: formData.language || null,
        location: formData.location || null,
        min_followers: formData.minFollowers ? parseInt(formData.minFollowers) : null,
        min_repos: formData.minRepos ? parseInt(formData.minRepos) : null,
        max_users: formData.maxUsers,
        per_user_repos: formData.perUserRepos
      };

      const response = await githubApi.fetchUsers(payload);
      if (response.job_id) {
        setJobId(response.job_id);
        onSearchStarted(response.job_id);
        toast({
          title: 'Search Started',
          description: 'GitHub search is running in the background...',
          status: 'info',
          duration: 3000,
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error.message,
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box as="form" onSubmit={handleSubmit} width="100%">
      <VStack spacing={4}>
        <FormControl>
          <FormLabel>Programming Language</FormLabel>
          <Input
            value={formData.language}
            onChange={(e) => setFormData({...formData, language: e.target.value})}
            placeholder="e.g., python, javascript, java"
          />
        </FormControl>

        <FormControl>
          <FormLabel>Location</FormLabel>
          <Input
            value={formData.location}
            onChange={(e) => setFormData({...formData, location: e.target.value})}
            placeholder="e.g., india, usa, london"
          />
        </FormControl>

        <FormControl>
          <FormLabel>Minimum Followers</FormLabel>
          <NumberInput
            value={formData.minFollowers}
            onChange={(valueString) => setFormData({...formData, minFollowers: valueString})}
            min={0}
          >
            <NumberInputField placeholder="e.g., 10" />
          </NumberInput>
        </FormControl>

        <FormControl>
          <FormLabel>Minimum Repositories</FormLabel>
          <Text fontSize="sm" color="gray.600" mb={2}>
            Filter for users who have at least this many public repositories
          </Text>
          <NumberInput
            value={formData.minRepos}
            onChange={(valueString) => setFormData({...formData, minRepos: valueString})}
            min={0}
          >
            <NumberInputField placeholder="e.g., 5" />
          </NumberInput>
        </FormControl>

        <FormControl>
          <FormLabel>Max Users to Fetch</FormLabel>
          <Text fontSize="sm" color="gray.600" mb={2}>
            Maximum number of GitHub users to retrieve and analyze
          </Text>
          <NumberInput
            value={formData.maxUsers}
            onChange={(valueString) => setFormData({...formData, maxUsers: parseInt(valueString)})}
            min={1}
            max={100}
          >
            <NumberInputField />
          </NumberInput>
        </FormControl>

        <FormControl>
          <FormLabel>Repositories to Analyze</FormLabel>
          <Text fontSize="sm" color="gray.600" mb={2}>
            Number of each user's latest repositories to analyze for skills
          </Text>
          <NumberInput
            value={formData.perUserRepos}
            onChange={(valueString) => setFormData({...formData, perUserRepos: parseInt(valueString)})}
            min={1}
            max={10}
          >
            <NumberInputField />
          </NumberInput>
        </FormControl>

        <Button
          type="submit"
          colorScheme="green"
          isLoading={isLoading}
          width="full"
        >
          Search GitHub
        </Button>
      </VStack>
    </Box>
  );
};