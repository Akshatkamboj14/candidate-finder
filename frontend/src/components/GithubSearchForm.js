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
  Card,
  CardBody,
  SimpleGrid,
  Icon,
  HStack,
  Badge,
  useColorModeValue,
  Divider,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  FormHelperText,
} from '@chakra-ui/react';
import { githubApi } from '../services/api';

// GitHub icon
const GitHubIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
  </svg>
);

const GithubSearchForm = ({ onSearchStarted, onCandidatesFound }) => {
  const [formData, setFormData] = React.useState({
    language: '',
    location: '',
    minFollowers: '',
    minRepos: '',
    maxUsers: 5,  // Editable default value
    perUserRepos: 3  // Editable default value
  });
  const [isLoading, setIsLoading] = React.useState(false);
  const [jobId, setJobId] = React.useState(null);
  const [errors, setErrors] = React.useState({});
  
  // New state for default values that can be edited
  const [defaultSettings, setDefaultSettings] = React.useState({
    maxUsers: 5,
    perUserRepos: 3
  });
  
  const toast = useToast();

  const cardBg = useColorModeValue('white', 'gray.800');
  const inputBg = useColorModeValue('gray.50', 'gray.700');
  
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
    
    // Validation
    const newErrors = {};
    
    if (!formData.language.trim()) {
      newErrors.language = 'Programming language is required';
    }
    
    if (isNaN(Number(formData.maxUsers)) || Number(formData.maxUsers) < 1) {
      newErrors.maxUsers = 'Max users must be a valid number (minimum 1)';
    }
    
    if (isNaN(Number(formData.perUserRepos)) || Number(formData.perUserRepos) < 1) {
      newErrors.perUserRepos = 'Repositories to analyze must be a valid number (minimum 1)';
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      toast({
        title: 'Validation Error',
        description: 'Please fix the errors in the form',
        status: 'error',
        duration: 3000,
      });
      return;
    }
    
    setErrors({});
    setIsLoading(true);
    try {
      // Convert and validate numbers properly
      const payload = {
        language: formData.language || null,
        location: formData.location || null,
        min_followers: formData.minFollowers ? parseInt(formData.minFollowers) : null,
        min_repos: formData.minRepos ? parseInt(formData.minRepos) : null,
        max_users: parseInt(formData.maxUsers) || 5,  // Default fallback
        per_user_repos: parseInt(formData.perUserRepos) || 3  // Default fallback
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

  // Function to update default settings
  const updateDefaultSettings = (key, value) => {
    const numValue = parseInt(value) || (key === 'maxUsers' ? 5 : 3);
    setDefaultSettings(prev => ({ ...prev, [key]: numValue }));
    // Also update current form data if it matches the old default
    setFormData(prev => ({ ...prev, [key]: numValue }));
  };

  // Function to reset form to default values
  const resetToDefaults = () => {
    setFormData({
      language: '',
      location: '',
      minFollowers: '',
      minRepos: '',
      maxUsers: defaultSettings.maxUsers,
      perUserRepos: defaultSettings.perUserRepos
    });
    setErrors({});
    toast({
      title: 'Form Reset',
      description: 'Form has been reset to default values',
      status: 'info',
      duration: 2000,
    });
  };

  return (
    <Card width="100%" bg={cardBg} shadow="xl" borderRadius="2xl" overflow="hidden">
      <CardBody p={8}>
        <VStack spacing={6}>
          {/* Header */}
          <Box textAlign="center" width="100%">
            <HStack justify="center" spacing={2} mb={2}>
              <Icon as={GitHubIcon} boxSize={6} color="purple.500" />
              <Text fontSize="xl" fontWeight="bold" color="gray.700">
                GitHub User Discovery
              </Text>
            </HStack>
            <Text color="gray.500" fontSize="sm">
              Search and analyze GitHub profiles based on your criteria
            </Text>
          </Box>

          <Divider />

          <Box as="form" onSubmit={handleSubmit} width="100%">
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
              {/* Essential Fields */}
              <FormControl isInvalid={errors.language} isRequired>
                <FormLabel fontWeight="semibold" color="gray.700">
                  🔤 Programming Language *
                </FormLabel>
                <Input
                  value={formData.language}
                  onChange={(e) => setFormData({...formData, language: e.target.value})}
                  placeholder="e.g., javascript, python, java, go"
                  bg={inputBg}
                  borderRadius="lg"
                  _hover={{ borderColor: "purple.300" }}
                  _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                />
                {errors.language && (
                  <Text color="red.500" fontSize="sm" mt={1}>
                    {errors.language}
                  </Text>
                )}
              </FormControl>

              <FormControl>
                <FormLabel fontWeight="semibold" color="gray.700">
                  📍 Location
                </FormLabel>
                <Input
                  value={formData.location}
                  onChange={(e) => setFormData({...formData, location: e.target.value})}
                  placeholder="e.g., India, USA, London, Remote"
                  bg={inputBg}
                  borderRadius="lg"
                  _hover={{ borderColor: "purple.300" }}
                  _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                />
              </FormControl>

              {/* Advanced Filters */}
              <FormControl>
                <FormLabel fontWeight="semibold" color="gray.700">
                  👥 Minimum Followers
                </FormLabel>
                <Text fontSize="xs" color="gray.500" mb={2}>
                  Filter for users with social proof
                </Text>
                <NumberInput
                  value={formData.minFollowers}
                  onChange={(valueString) => setFormData({...formData, minFollowers: valueString})}
                  min={0}
                >
                  <NumberInputField 
                    placeholder="e.g., 50" 
                    bg={inputBg}
                    borderRadius="lg"
                    _hover={{ borderColor: "purple.300" }}
                    _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                  />
                </NumberInput>
              </FormControl>

              <FormControl>
                <FormLabel fontWeight="semibold" color="gray.700">
                  📚 Minimum Repositories
                </FormLabel>
                <Text fontSize="xs" color="gray.500" mb={2}>
                  Filter for active developers
                </Text>
                <NumberInput
                  value={formData.minRepos}
                  onChange={(valueString) => setFormData({...formData, minRepos: valueString})}
                  min={0}
                >
                  <NumberInputField 
                    placeholder="e.g., 10" 
                    bg={inputBg}
                    borderRadius="lg"
                    _hover={{ borderColor: "purple.300" }}
                    _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                  />
                </NumberInput>
              </FormControl>

              {/* Analysis Settings */}
              <FormControl isInvalid={errors.maxUsers} isRequired>
                <FormLabel fontWeight="semibold" color="gray.700">
                  🎯 Max Users to Fetch *
                </FormLabel>
                <HStack spacing={2} mb={2}>
                  <Badge colorScheme="blue" variant="outline" size="sm">Recommended: 5-20</Badge>
                  <Badge colorScheme="yellow" variant="outline" size="sm">Max: 100</Badge>
                </HStack>
                <NumberInput
                  value={formData.maxUsers}
                  onChange={(valueString, valueNumber) => {
                    // Proper NaN handling
                    const safeValue = isNaN(valueNumber) ? 5 : valueNumber;
                    setFormData({...formData, maxUsers: safeValue});
                  }}
                  min={1}
                  max={100}
                >
                  <NumberInputField 
                    bg={inputBg}
                    borderRadius="lg"
                    _hover={{ borderColor: "purple.300" }}
                    _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                  />
                </NumberInput>
                {errors.maxUsers && (
                  <Text color="red.500" fontSize="sm" mt={1}>
                    {errors.maxUsers}
                  </Text>
                )}
              </FormControl>

              <FormControl isInvalid={errors.perUserRepos} isRequired>
                <FormLabel fontWeight="semibold" color="gray.700">
                  🔍 Repos per User *
                </FormLabel>
                <HStack spacing={2} mb={2}>
                  <Badge colorScheme="green" variant="outline" size="sm">Recommended: 3-5</Badge>
                  <Badge colorScheme="orange" variant="outline" size="sm">Max: 10</Badge>
                </HStack>
                <NumberInput
                  value={formData.perUserRepos}
                  onChange={(valueString, valueNumber) => {
                    // Proper NaN handling
                    const safeValue = isNaN(valueNumber) ? 3 : valueNumber;
                    setFormData({...formData, perUserRepos: safeValue});
                  }}
                  min={1}
                  max={10}
                >
                  <NumberInputField 
                    bg={inputBg}
                    borderRadius="lg"
                    _hover={{ borderColor: "purple.300" }}
                    _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                  />
                </NumberInput>
                {errors.perUserRepos && (
                  <Text color="red.500" fontSize="sm" mt={1}>
                    {errors.perUserRepos}
                  </Text>
                )}
              </FormControl>
            </SimpleGrid>

            {/* Advanced Settings */}
            <Box mt={6}>
              <Accordion allowToggle>
                <AccordionItem border="1px solid" borderColor="gray.200" borderRadius="lg">
                  <AccordionButton
                    _hover={{ bg: "purple.50" }}
                    _expanded={{ bg: "purple.100", color: "purple.700" }}
                    borderRadius="lg"
                  >
                    <Box flex="1" textAlign="left">
                      <HStack>
                        <Text fontWeight="semibold">⚙️ Default Settings</Text>
                        <Badge colorScheme="purple" variant="subtle" size="sm">
                          Customizable
                        </Badge>
                      </HStack>
                    </Box>
                    <AccordionIcon />
                  </AccordionButton>
                  <AccordionPanel pb={4}>
                    <Text fontSize="sm" color="gray.600" mb={4}>
                      Customize the default values that will be used when you reset the form or start fresh.
                    </Text>
                    
                    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                      <FormControl>
                        <FormLabel fontSize="sm" fontWeight="semibold">
                          Default Max Users
                        </FormLabel>
                        <NumberInput
                          value={defaultSettings.maxUsers}
                          onChange={(valueString) => updateDefaultSettings('maxUsers', valueString)}
                          min={1}
                          max={100}
                        >
                          <NumberInputField
                            bg="gray.50"
                            borderRadius="lg"
                            _hover={{ borderColor: "purple.300" }}
                            _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                          />
                        </NumberInput>
                        <FormHelperText fontSize="xs">
                          Default: 5 users per search
                        </FormHelperText>
                      </FormControl>

                      <FormControl>
                        <FormLabel fontSize="sm" fontWeight="semibold">
                          Default Repos per User
                        </FormLabel>
                        <NumberInput
                          value={defaultSettings.perUserRepos}
                          onChange={(valueString) => updateDefaultSettings('perUserRepos', valueString)}
                          min={1}
                          max={20}
                        >
                          <NumberInputField
                            bg="gray.50"
                            borderRadius="lg"
                            _hover={{ borderColor: "purple.300" }}
                            _focus={{ borderColor: "purple.500", bg: "purple.50" }}
                          />
                        </NumberInput>
                        <FormHelperText fontSize="xs">
                          Default: 3 repositories per user
                        </FormHelperText>
                      </FormControl>
                    </SimpleGrid>

                    <HStack mt={4} spacing={3}>
                      <Button
                        size="sm"
                        variant="outline"
                        colorScheme="purple"
                        onClick={resetToDefaults}
                      >
                        🔄 Reset Form to Defaults
                      </Button>
                      <Badge colorScheme="green" variant="subtle">
                        Settings auto-save
                      </Badge>
                    </HStack>
                  </AccordionPanel>
                </AccordionItem>
              </Accordion>
            </Box>

            <Button
              type="submit"
              colorScheme="purple"
              size="lg"
              isLoading={isLoading}
              width="full"
              mt={8}
              leftIcon={<GitHubIcon />}
              bgGradient="linear(to-r, purple.500, pink.500)"
              _hover={{
                bgGradient: "linear(to-r, purple.600, pink.600)",
                transform: "translateY(-2px)",
                shadow: "lg"
              }}
              transition="all 0.2s"
              borderRadius="xl"
              py={6}
              fontSize="lg"
              fontWeight="bold"
              loadingText="🔍 Searching GitHub..."
            >
              🚀 Discover GitHub Talent
            </Button>
          </Box>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default GithubSearchForm;