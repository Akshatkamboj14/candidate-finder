import React from 'react';
import {
  Box,
  Container,
  Heading,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  VStack,
} from '@chakra-ui/react';
import { JobForm } from './components/JobForm';
import { GithubSearchForm } from './components/GithubSearchForm';
import { CandidateList } from './components/CandidateList';
import { ExistingCandidatesList } from './components/ExistingCandidatesList';
import K8sQueryForm from './components/K8sQueryForm';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

function App() {
  const [jobResults, setJobResults] = React.useState(null);
  const [githubJobId, setGithubJobId] = React.useState(null);
  const [githubResults, setGithubResults] = React.useState(null);

  const handleJobCreated = (results) => {
    setJobResults(results);
  };

  const handleGithubSearchStarted = (jobId) => {
    setGithubJobId(jobId);
    setGithubResults(null); // Clear previous results
  };

  const handleGithubCandidatesFound = (candidates) => {
    setGithubResults(candidates);
    setGithubJobId(null); // Clear job ID as search is complete
  };

  return (
    <QueryClientProvider client={queryClient}>
      <Box minH="100vh" bg="gray.50" py={8}>
        <Container maxW="container.lg">
          <VStack spacing={8}>
            <Heading>Candidate Finder</Heading>
            
            <Tabs width="100%" variant="enclosed">
              <TabList>
                <Tab>Find by Job Description</Tab>
                <Tab>Search GitHub Users</Tab>
                <Tab>View All Candidates</Tab>
                <Tab>K8s Assistant</Tab>
              </TabList>
              
              <TabPanels>
                <TabPanel>
                  <VStack spacing={6}>
                    <JobForm onJobCreated={handleJobCreated} />
                    {jobResults?.results && (
                      <Box width="100%">
                        <Heading size="md" mb={4}>Matching Candidates</Heading>
                        <CandidateList candidates={jobResults.results} />
                      </Box>
                    )}
                  </VStack>
                </TabPanel>
                
                <TabPanel>
                  <VStack spacing={6}>
                    <GithubSearchForm 
                      onSearchStarted={handleGithubSearchStarted}
                      onCandidatesFound={handleGithubCandidatesFound}
                    />
                    {githubJobId && (
                      <Box width="100%">
                        <Heading size="md" mb={4}>
                          Searching GitHub... Job ID: {githubJobId}
                        </Heading>
                      </Box>
                    )}
                    {githubResults && (
                      <Box width="100%">
                        <Heading size="md" mb={4}>Found Candidates</Heading>
                        <CandidateList candidates={githubResults} />
                      </Box>
                    )}
                  </VStack>
                </TabPanel>

                <TabPanel>
                  <ExistingCandidatesList />
                </TabPanel>

                <TabPanel>
                  <K8sQueryForm />
                </TabPanel>
              </TabPanels>
            </Tabs>
          </VStack>
        </Container>
      </Box>
    </QueryClientProvider>
  );
}

export default App;