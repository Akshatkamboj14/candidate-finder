import React from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Textarea,
  VStack,
  useToast
} from '@chakra-ui/react';
import { jobsApi } from '../services/api';

export const JobForm = ({ onJobCreated }) => {
  const [jd, setJd] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!jd.trim()) {
      toast({
        title: 'Error',
        description: 'Please enter a job description',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      const response = await jobsApi.createJob(jd);
      onJobCreated(response);
      toast({
        title: 'Success',
        description: 'Job created successfully',
        status: 'success',
        duration: 3000,
      });
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
          <FormLabel>Job Description</FormLabel>
          <Textarea
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Enter the job description here..."
            size="lg"
            rows={10}
          />
        </FormControl>
        <Button
          type="submit"
          colorScheme="blue"
          isLoading={isLoading}
          width="full"
        >
          Find Candidates
        </Button>
      </VStack>
    </Box>
  );
};