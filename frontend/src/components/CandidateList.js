import React from 'react';
import {
  Box,
  Card,
  CardBody,
  Heading,
  Stack,
  Text,
  Badge,
  VStack,
  SimpleGrid,
  Button,
  Flex,
  Wrap,
  WrapItem,
  UnorderedList,
  ListItem,
} from '@chakra-ui/react';
import { ExternalLinkIcon } from '@chakra-ui/icons';

export const CandidateList = ({ candidates }) => {
  if (!candidates?.length) {
    return <Text>No candidates found.</Text>;
  }

  const parseSkills = (skillsData) => {
    try {
      if (!skillsData) return [];
      if (Array.isArray(skillsData)) return skillsData;
      return JSON.parse(skillsData);
    } catch (e) {
      return [];
    }
  };

  return (
    <VStack spacing={4} width="100%">
      {candidates.map((candidate) => {
        const skills = parseSkills(candidate.metadata?.skills_list || candidate.metadata?.skills_list_json);
        
        return (
          <Card key={candidate.id} width="100%">
            <CardBody>
                <Stack spacing={4}>
                {/* Header with name, profile link, and semantic match score */}
                <Flex 
                  justify="space-between" 
                  align="flex-start"
                  flexDir={{ base: "column", md: "row" }}
                  gap={3}
                >
                  <Box flex="1">
                    <Flex align="center" gap={3}>
                      <Heading size="md">
                        {candidate.metadata?.name || candidate.metadata?.username || candidate.id}
                      </Heading>
                      <Badge 
                        colorScheme={
                          candidate.confidence === "HIGH" ? "green" :
                          candidate.confidence === "MEDIUM" ? "yellow" : "gray"
                        }
                        fontSize="sm"
                      >
                        {candidate.similarity_score}% Match
                      </Badge>
                      <Badge 
                        colorScheme={
                          candidate.confidence === "HIGH" ? "green" :
                          candidate.confidence === "MEDIUM" ? "yellow" : "red"
                        }
                      >
                        {candidate.confidence} Confidence
                      </Badge>
                    </Flex>
                    {candidate.metadata?.bio && (
                      <Text color="gray.600" mt={1}>
                        {candidate.metadata.bio}
                      </Text>
                    )}
                  </Box>                  <Flex gap={2} flexWrap="wrap">
                    {candidate.metadata?.profile_url && (
                      <Button 
                        as="a" 
                        href={candidate.metadata.profile_url}
                        target="_blank" 
                        rel="noopener noreferrer"
                        size="sm"
                        colorScheme="blue"
                        leftIcon={<ExternalLinkIcon />}
                      >
                        GitHub Profile
                      </Button>
                    )}
                    {candidate.metadata?.blog && (
                      <Button
                        as="a"
                        href={candidate.metadata.blog.startsWith('http') ? candidate.metadata.blog : `https://${candidate.metadata.blog}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        size="sm"
                        variant="outline"
                        colorScheme="blue"
                        leftIcon={<ExternalLinkIcon />}
                      >
                        Website
                      </Button>
                    )}
                  </Flex>
                </Flex>

                {/* Basic Info Grid */}
                <SimpleGrid columns={[1, 2]} spacing={3}>
                  {candidate.metadata?.location && (
                    <Box>
                      <Text fontWeight="bold">Location:</Text>
                      <Text>{candidate.metadata.location}</Text>
                    </Box>
                  )}
                  {candidate.metadata?.company && (
                    <Box>
                      <Text fontWeight="bold">Company:</Text>
                      <Text>{candidate.metadata.company}</Text>
                    </Box>
                  )}
                  {candidate.metadata?.public_repos && (
                    <Box>
                      <Text fontWeight="bold">Public Repos:</Text>
                      <Text>{candidate.metadata.public_repos}</Text>
                    </Box>
                  )}
                  {candidate.metadata?.followers && (
                    <Box>
                      <Text fontWeight="bold">Followers:</Text>
                      <Text>{candidate.metadata.followers}</Text>
                    </Box>
                  )}
                </SimpleGrid>

                {/* Skills Section with Evidence */}
                {(skills.length > 0 || candidate.metadata?.skills_evidence_json) && (
                  <Box>
                    <Text fontWeight="bold" fontSize="lg" mb={3}>Skills & Evidence:</Text>
                    
                    {/* Summary Skills */}
                    {skills.length > 0 && (
                      <Box mb={4}>
                        <Text fontWeight="semibold" mb={2} color="blue.600">Summary:</Text>
                        <Wrap>
                          {skills.map((skill) => (
                            <WrapItem key={skill}>
                              <Badge colorScheme="blue" p={2} borderRadius="full">
                                {skill}
                              </Badge>
                            </WrapItem>
                          ))}
                        </Wrap>
                      </Box>
                    )}
                    
                    {/* Detailed Evidence */}
                    {candidate.metadata?.skills_evidence_json && (
                      <Box>
                        <Text fontWeight="semibold" mb={2} color="blue.600">Detailed Evidence:</Text>
                        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                          {Object.entries(
                            typeof candidate.metadata.skills_evidence_json === 'string' 
                              ? JSON.parse(candidate.metadata.skills_evidence_json)
                              : candidate.metadata.skills_evidence_json
                          ).map(([skill, evidence]) => (
                            <Box 
                              key={skill} 
                              p={4} 
                              bg="gray.50" 
                              borderRadius="md"
                              border="1px"
                              borderColor="gray.200"
                              _hover={{ shadow: 'md' }}
                            >
                              <Flex justify="space-between" align="center" mb={2}>
                                <Text fontWeight="bold" color="blue.600">
                                  {skill}
                                </Text>
                                <Badge colorScheme="green" variant="subtle">
                                  {Array.isArray(evidence) ? evidence.length : 1} reference{Array.isArray(evidence) && evidence.length !== 1 ? 's' : ''}
                                </Badge>
                              </Flex>
                              <Box 
                                maxH="200px" 
                                overflowY="auto"
                                css={{
                                  '&::-webkit-scrollbar': {
                                    width: '4px',
                                  },
                                  '&::-webkit-scrollbar-track': {
                                    width: '6px',
                                    background: 'transparent',
                                  },
                                  '&::-webkit-scrollbar-thumb': {
                                    background: 'var(--chakra-colors-blue-200)',
                                    borderRadius: '24px',
                                  },
                                }}
                              >
                                {Array.isArray(evidence) ? (
                                  <UnorderedList spacing={2}>
                                    {evidence.map((item, idx) => (
                                      <ListItem key={idx} fontSize="sm">
                                        {item}
                                      </ListItem>
                                    ))}
                                  </UnorderedList>
                                ) : (
                                  <Text fontSize="sm">{evidence}</Text>
                                )}
                              </Box>
                            </Box>
                          ))}
                        </SimpleGrid>
                      </Box>
                    )}
                  </Box>
                )}

                {/* Repository Links */}
                {candidate.metadata?.top_repositories && (
                  <Box>
                    <Text fontWeight="bold" fontSize="lg" mb={3}>Top Repositories:</Text>
                    <SimpleGrid columns={{ base: 1, sm: 2, md: 3 }} spacing={3}>
                      {JSON.parse(candidate.metadata.top_repositories).slice(0, 6).map((repo, index) => (
                        <Box
                          key={index}
                          p={4}
                          bg="gray.50"
                          borderRadius="lg"
                          borderWidth="1px"
                          borderColor="gray.200"
                          _hover={{ shadow: 'md', borderColor: 'blue.200' }}
                        >
                          <VStack align="stretch" spacing={2}>
                            <Flex justify="space-between" align="center">
                              <Heading size="sm" color="blue.600">
                                <a 
                                  href={repo.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  style={{ textDecoration: 'none' }}
                                >
                                  {repo.name}
                                </a>
                              </Heading>
                              <Flex align="center" gap={1}>
                                <Box as="span" color="yellow.400" fontSize="lg">★</Box>
                                <Text fontSize="sm" fontWeight="bold" color="gray.600">
                                  {repo.stars?.toLocaleString() || 0}
                                </Text>
                              </Flex>
                            </Flex>
                            {repo.description && (
                              <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                {repo.description}
                              </Text>
                            )}
                            {repo.language && (
                              <Badge alignSelf="flex-start" colorScheme="blue">
                                {repo.language}
                              </Badge>
                            )}
                          </VStack>
                        </Box>
                      ))}
                    </SimpleGrid>
                  </Box>
                )}

                {/* Detailed Information */}
                <Box>
                  <Text fontWeight="bold" mb={2}>Profile Details:</Text>
                  <VStack align="stretch" spacing={2}>
                    {Object.entries(candidate.metadata || {}).map(([key, value]) => {
                      // Skip certain metadata fields we don't want to display
                      if ([
                        'repository_urls',
                        'id',
                        'html_url',
                        'skills_list',
                        'skills_list_json',
                        'skills_evidence',
                        'skills_evidence_json',
                        'top_repositories'  // Add this to exclude the repository JSON from Profile Details
                      ].includes(key)) return null;
                      if (!value) return null;
                      
                      return (
                        <Box key={key} p={2} bg="gray.50" borderRadius="md">
                          <Text as="span" fontWeight="bold" color="blue.600">
                            {key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}:
                          </Text>
                          {' '}
                          <Text as="span">{String(value)}</Text>
                        </Box>
                      );
                    })}
                  </VStack>
                </Box>

              </Stack>
            </CardBody>
          </Card>
        );
      })}
    </VStack>
  );
};