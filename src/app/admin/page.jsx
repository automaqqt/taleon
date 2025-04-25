"use client"

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import styles from '../../styles/Admin.module.css';
import * as authService from '../../services/auth';

export default function AdminPage() {
  const router = useRouter();
  
  // --- Authentication State ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminCredentials, setAdminCredentials] = useState(null);
  
  // --- UI State ---
  const [activeView, setActiveView] = useState('baseStories'); // baseStories, editBaseStory, createBaseStory, createPrompt
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  
  // --- Data State ---
  const [baseStories, setBaseStories] = useState([]);
  const [selectedBaseStory, setSelectedBaseStory] = useState(null);
  const [storyPrompts, setStoryPrompts] = useState([]);
  
  // --- Form State ---
  const [baseStoryForm, setBaseStoryForm] = useState({
    title: '',
    description: '',
    original_tale_context: '',
    initial_system_prompt: '',
    initial_summary: '',
    language: 'Deutsch'
  });
  
  const [promptForm, setPromptForm] = useState({
    name: '',
    system_prompt: '',
    turn_start: 0,
    turn_end: null
  });

  // --- Authentication Effects ---
  useEffect(() => {
    // Check if user is already logged in
    const user = authService.getCurrentUser();
    const adminCreds = authService.getAdminCredentials();
    
    if (user && adminCreds) {
      setIsAuthenticated(true);
      setIsAdmin(true);
      setAdminCredentials(adminCreds);
      loadBaseStories();
    } else {
      // Redirect to login if not admin
      router.push('/');
    }
  }, [router]);

  // --- Data Loading Functions ---
  async function loadBaseStories() {
    if (!adminCredentials) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const stories = await authService.getBaseStories();
      setBaseStories(stories);
    } catch (err) {
      console.error("Error loading base stories:", err);
      setError(`Failed to load stories: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadBaseStoryDetails(storyId) {
    if (!adminCredentials) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const storyDetails = await authService.adminGetBaseStory(storyId, adminCredentials);
      setSelectedBaseStory(storyDetails);
      setStoryPrompts(storyDetails.story_prompts || []);
      
      // Update form with story details
      setBaseStoryForm({
        title: storyDetails.title,
        description: storyDetails.description,
        original_tale_context: storyDetails.original_tale_context,
        initial_system_prompt: storyDetails.initial_system_prompt,
        initial_summary: storyDetails.initial_summary,
        language: storyDetails.language || 'Deutsch'
      });
      
      setActiveView('editBaseStory');
    } catch (err) {
      console.error("Error loading base story details:", err);
      setError(`Failed to load story details: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  // --- Form Submission Handlers ---
  async function handleCreateBaseStory(e) {
    e.preventDefault();
    if (!adminCredentials) return;
    
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      const result = await authService.adminCreateBaseStory(baseStoryForm, adminCredentials);
      
      if (result && result.success) {
        setSuccessMessage(`Successfully created "${result.title}" story template!`);
        
        // Reset form and reload stories
        setBaseStoryForm({
          title: '',
          description: '',
          original_tale_context: '',
          initial_system_prompt: '',
          initial_summary: '',
          language: 'Deutsch'
        });
        
        setTimeout(() => {
          loadBaseStories();
          setActiveView('baseStories');
        }, 1500);
      }
    } catch (err) {
      console.error("Error creating base story:", err);
      setError(`Failed to create story: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpdateBaseStory(e) {
    e.preventDefault();
    if (!adminCredentials || !selectedBaseStory) return;
    
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      const result = await authService.adminUpdateBaseStory(
        selectedBaseStory.id, 
        baseStoryForm, 
        adminCredentials
      );
      
      if (result && result.success) {
        setSuccessMessage(`Successfully updated "${result.title}" story template!`);
        
        setTimeout(() => {
          loadBaseStories();
          setActiveView('baseStories');
        }, 1500);
      }
    } catch (err) {
      console.error("Error updating base story:", err);
      setError(`Failed to update story: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreatePrompt(e) {
    e.preventDefault();
    if (!adminCredentials) return;
    
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    
    // Add base_story_id to the form data if we're in edit mode
    const promptData = { ...promptForm };
    if (selectedBaseStory) {
        promptData.base_story_id = selectedBaseStory.id;
        
    console.log(selectedBaseStory)
    }
    
    try {
        const result = await authService.adminCreateStoryPrompt(promptData, adminCredentials);
        
        if (result && result.success) {
            setSuccessMessage(`Successfully created "${result.name}" prompt!`);
            
            // No need to separately assign the prompt - it's already assigned
            // if we included base_story_id
            
            if (selectedBaseStory && activeView === 'editBaseStory') {
                // Just reload the base story details to show the new prompt
                setTimeout(() => {
                    loadBaseStoryDetails(selectedBaseStory.id);
                }, 1000);
            } else {
                // Reset form and go back to main view
                setPromptForm({
                    name: '',
                    system_prompt: '',
                    turn_start: 0,
                    turn_end: null
                });
                
                setTimeout(() => {
                    setActiveView('baseStories');
                }, 1500);
            }
        }
    } catch (err) {
        console.error("Error creating prompt:", err);
        setError(`Failed to create prompt: ${err.message}`);
    } finally {
        setIsLoading(false);
    }
}

  async function handleToggleStoryActive(storyId, active) {
    if (!adminCredentials) return;
    
    setIsLoading(true);
    
    try {
      await authService.adminToggleBaseStory(storyId, active, adminCredentials);
      
      // Update local state
      setBaseStories(prev => 
        prev.map(story => 
          story.id === storyId ? { ...story, is_active: active } : story
        )
      );
      
      setSuccessMessage(`Story ${active ? 'activated' : 'deactivated'} successfully!`);
      setTimeout(() => setSuccessMessage(null), 2000);
    } catch (err) {
      console.error(`Error toggling story active state:`, err);
      setError(`Failed to update story: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  // --- Form Change Handlers ---
  const handleBaseStoryFormChange = (e) => {
    const { name, value } = e.target;
    setBaseStoryForm(prev => ({
      ...prev,
      [name]: value
    }));
  };


  const handlePromptFormChange = (e) => {
    const { name, value } = e.target;
    setPromptForm(prev => ({
      ...prev,
      [name]: name === 'turn_start' ? parseInt(value, 10) : (
        name === 'turn_end' ? (value === '' ? null : parseInt(value, 10)) : value
      )
    }));
  };

  // --- UI Navigation Handlers ---
  const navigateToCreateBaseStory = () => {
    setBaseStoryForm({
      title: '',
      description: '',
      original_tale_context: '',
      initial_system_prompt: '',
      initial_summary: '',
      language: 'Deutsch'
    });
    setActiveView('createBaseStory');
  };

  const navigateToCreatePrompt = () => {
    setPromptForm({
      name: '',
      system_prompt: '',
      turn_start: 0,
      turn_end: null
    });
    setActiveView('createPrompt');
  };

  const navigateToMain = () => {
    setActiveView('baseStories');
    setSelectedBaseStory(null);
    loadBaseStories();
  };

  const handleDeletePrompt = async (promptId, promptName) => {
    if (!adminCredentials || !selectedBaseStory) return;

    // Provide prompt name in confirmation for clarity
    if (window.confirm(`Are you sure you want to permanently delete the prompt "${promptName}" (ID: ${promptId})? This will remove it from this story.`)) {
      setIsLoading(true);
      setError(null);
      setSuccessMessage(null);
      try {
        await authService.adminDeleteStoryPrompt(promptId, adminCredentials);
        setSuccessMessage(`Prompt "${promptName}" deleted successfully.`);
        // Refresh the story details to update the prompt list
        await loadBaseStoryDetails(selectedBaseStory.id); // Use await here
        // Clear success message after a delay
         setTimeout(() => setSuccessMessage(null), 3000);
      } catch (err) {
        console.error("Error deleting prompt:", err);
        setError(`Failed to delete prompt: ${err.message}`);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleDeleteBaseStory = async (storyId, storyTitle) => {
     if (!adminCredentials || !storyId) return;

     // Stronger confirmation
     if (window.confirm(`!!! DESTRUCTIVE ACTION !!!\n\nAre you absolutely sure you want to permanently delete the base story "${storyTitle}" (ID: ${storyId})?\n\nThis cannot be undone and will fail if any users have started stories based on it.`)) {
        setIsLoading(true);
        setError(null);
        setSuccessMessage(null);
        try {
            await authService.adminDeleteBaseStory(storyId, adminCredentials);
            setSuccessMessage(`Base story "${storyTitle}" deleted successfully.`);
             // Navigate away after successful deletion
             setTimeout(() => {
                setSuccessMessage(null);
                navigateToMain(); // Go back to the main list view
             }, 2000); // Give time to see success message
        } catch (err) {
            console.error("Error deleting base story:", err);
            setError(`Failed to delete base story: ${err.message}`);
             setIsLoading(false); // Ensure loading is off on error
        }
        // No finally for isLoading here, handled by navigation/error path
     }
  };

  // If not authenticated or not admin, don't render anything (redirect happens in useEffect)
  if (!isAuthenticated || !isAdmin) {
    return <div className={styles.loading}>Checking credentials...</div>;
  }

  return (
    <div className={styles.adminContainer}>
      <header className={styles.adminHeader}>
        <h1>Taleon Admin Panel</h1>
        <div className={styles.adminNav}>
          <button 
            className={`${styles.navButton} ${activeView === 'baseStories' ? styles.active : ''}`} 
            onClick={navigateToMain}
          >
            All Base Stories
          </button>
          
          <button 
            className={styles.navButton} 
            onClick={navigateToCreateBaseStory}
          >
            Create New Base Story
          </button>
          
          
          <button 
            className={styles.logoutButton}
            onClick={() => {
              authService.logout();
              router.push('/');
            }}
          >
            Logout
          </button>
        </div>
      </header>

      <main className={styles.adminMain}>
        {isLoading && <div className={styles.loading}>Loading...</div>}
        
        {error && (
          <div className={styles.errorMessage}>
            <p>{error}</p>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}
        
        {successMessage && (
          <div className={styles.successMessage}>
            <p>{successMessage}</p>
          </div>
        )}

        {/* Base Stories List View */}
        {activeView === 'baseStories' && !isLoading && (
          <div className={styles.baseStoriesList}>
            <h2>Available Base Stories</h2>
            
            {baseStories.length === 0 ? (
              <p>No base stories found. Create one to get started!</p>
            ) : (
              <div className={styles.storiesGrid}>
                {baseStories.map(story => (
                  <div key={story.id} className={styles.storyCard}>
                    <h3>{story.title}</h3>
                    <p>{story.description}</p>
                    <p className={styles.storyMeta}>
                      Language: {story.language}
                      <span className={`${styles.activeStatus} ${story.is_active ? styles.active : styles.inactive}`}>
                        {story.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </p>
                    
                    <div className={styles.storyActions}>
                      <button 
                        className={styles.editButton}
                        onClick={() => loadBaseStoryDetails(story.id)}
                      >
                        Edit
                      </button>
                      
                      <button 
                        className={`${styles.toggleButton} ${story.is_active ? styles.deactivate : styles.activate}`}
                        onClick={() => handleToggleStoryActive(story.id, !story.is_active)}
                      >
                        {story.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Create Base Story View */}
        {activeView === 'createBaseStory' && (
          <div className={styles.formContainer}>
            <h2>Create New Base Story</h2>
            
            <form onSubmit={handleCreateBaseStory}>
              <div className={styles.formGroup}>
                <label htmlFor="title">Title</label>
                <input
                  type="text"
                  id="title"
                  name="title"
                  value={baseStoryForm.title}
                  onChange={handleBaseStoryFormChange}
                  required
                />
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="language">Language</label>
                <select
                  id="language"
                  name="language"
                  value={baseStoryForm.language}
                  onChange={handleBaseStoryFormChange}
                >
                  <option value="Deutsch">German</option>
                  <option value="English">English</option>
                  <option value="Français">French</option>
                  <option value="Español">Spanish</option>
                </select>
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="description">Description</label>
                <textarea
                  id="description"
                  name="description"
                  value={baseStoryForm.description}
                  onChange={handleBaseStoryFormChange}
                  rows="3"
                  required
                />
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="original_tale_context">Original Tale Context</label>
                <textarea
                  id="original_tale_context"
                  name="original_tale_context"
                  value={baseStoryForm.original_tale_context}
                  onChange={handleBaseStoryFormChange}
                  rows="5"
                  required
                />
                <small>Context from the original fairy tale that will be used for generation.</small>
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="initial_summary">Starting Point - give precise starting situation</label>
                <textarea
                  id="initial_summary"
                  name="initial_summary"
                  value={baseStoryForm.initial_summary}
                  onChange={handleBaseStoryFormChange}
                  rows="3"
                  required
                />
                <small>Starting summary for new stories.</small>
              </div>
              
              <div className={styles.formActions}>
                <button 
                  type="button" 
                  className={styles.cancelButton}
                  onClick={navigateToMain}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className={styles.submitButton}
                  disabled={isLoading}
                >
                  Create Base Story
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Edit Base Story View */}
        {activeView === 'editBaseStory' && selectedBaseStory && (
          <div className={styles.formContainer}>
            <h2>Edit Base Story: {selectedBaseStory.title}</h2>
            
            <form onSubmit={handleUpdateBaseStory}>
              <div className={styles.formGroup}>
                <label htmlFor="title">Title</label>
                <input
                  type="text"
                  id="title"
                  name="title"
                  value={baseStoryForm.title}
                  onChange={handleBaseStoryFormChange}
                  required
                />
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="language">Language</label>
                <select
                  id="language"
                  name="language"
                  value={baseStoryForm.language}
                  onChange={handleBaseStoryFormChange}
                >
                  <option value="Deutsch">German</option>
                  <option value="English">English</option>
                  <option value="Français">French</option>
                  <option value="Español">Spanish</option>
                </select>
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="description">Description</label>
                <textarea
                  id="description"
                  name="description"
                  value={baseStoryForm.description}
                  onChange={handleBaseStoryFormChange}
                  rows="3"
                  required
                />
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="original_tale_context">Original Tale Context</label>
                <textarea
                  id="original_tale_context"
                  name="original_tale_context"
                  value={baseStoryForm.original_tale_context}
                  onChange={handleBaseStoryFormChange}
                  rows="5"
                  required
                />
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="initial_summary">Initial Summary</label>
                <textarea
                  id="initial_summary"
                  name="initial_summary"
                  value={baseStoryForm.initial_summary}
                  onChange={handleBaseStoryFormChange}
                  rows="3"
                  required
                />
              </div>
              
              
              <div className={styles.formActions}>
                <button 
                  type="button" 
                  className={styles.cancelButton}
                  onClick={navigateToMain}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className={styles.submitButton}
                  disabled={isLoading}
                >
                  Update Base Story
                </button>
              </div>
            </form>
            {/* --- Initial Elements Display --- */}
            {/* Check specifically for the key in the object */}
            {selectedBaseStory.initial_story_elements && Object.keys(selectedBaseStory.initial_story_elements).length > 0 ? (
              <div className={styles.initialElementsSection}> {/* Added a wrapper class */}
                <h4>Initial Story Elements (Auto-Extracted)</h4>
                <pre className={styles.jsonDisplay}> {/* Added a class for styling */}
                  {JSON.stringify(selectedBaseStory.initial_story_elements, null, 2)}
                </pre>
                <p><small>This data is used to pre-fill new user stories based on this template. It's generated automatically when creating a story.</small></p>
              </div>
            ) : (
                 <div className={styles.initialElementsSection}>
                    <h4>Initial Story Elements</h4>
                    <p>No initial elements were extracted or stored for this story.</p>
                 </div>
            )}


            {/* --- Prompts Section --- */}
            <div className={styles.promptsSection}>
              <h3>Story Prompts</h3>
              {selectedBaseStory.story_prompts && selectedBaseStory.story_prompts.length > 0 ? (
                <div className={styles.promptsList}>
                  {selectedBaseStory.story_prompts.map(prompt => (
                    <div key={prompt.id} className={styles.promptItem}>
                      <div className={styles.promptHeader}>
                          <h4>{prompt.name}</h4>
                          {/* Delete Button */}
                          <button
                              onClick={() => handleDeletePrompt(prompt.id, prompt.name)}
                              className={styles.deleteButtonSmall} // Use a specific class
                              title="Delete this prompt"
                              disabled={isLoading}
                          >
                              Delete Prompt
                          </button>
                      </div>
                      <p>Turns: {prompt.turn_start} - {prompt.turn_end ?? 'End'}</p>
                      <details>
                        <summary>View Prompt Text</summary>
                        <pre className={styles.promptTextDisplay}>{prompt.system_prompt}</pre>
                      </details>
                    </div>
                  ))}
                </div>
              ) : (
                <p>No prompts assigned to this story yet.</p>
              )}

              <button
                className={styles.addPromptButton}
                onClick={() => {
                  setPromptForm({ name: '', system_prompt: '', turn_start: 0, turn_end: null });
                  setActiveView('createPrompt'); // Navigate to create prompt view
                }}
                disabled={isLoading}
              >
                Add New Prompt to This Story
              </button>
            </div>

            {/* --- Delete Base Story Section --- */}
            <div className={styles.deleteSection}>
               <h3>Delete Base Story</h3>
               <p className={styles.warningText}>
                   Warning: Deleting a base story is permanent and cannot be undone.
                   Deletion will fail if any user has started a story based on this template.
               </p>
               <button
                   onClick={() => handleDeleteBaseStory(selectedBaseStory.id, selectedBaseStory.title)}
                   className={styles.deleteButtonLarge} // Use a specific class
                   disabled={isLoading}
               >
                   Delete "{selectedBaseStory.title}" Base Story
               </button>
            </div>

          </div>
        )}

        {/* Create Prompt View */}
        {activeView === 'createPrompt' && (
          <div className={styles.formContainer}>
            <h2>Create New Story Prompt</h2>
            
            {selectedBaseStory && (
              <p className={styles.assignmentNote}>
                This prompt will be assigned to: <strong>{selectedBaseStory.title}</strong>
              </p>
            )}
            
            <form onSubmit={handleCreatePrompt}>
              <div className={styles.formGroup}>
                <label htmlFor="name">Prompt Name</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={promptForm.name}
                  onChange={handlePromptFormChange}
                  required
                />
              </div>
              
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label htmlFor="turn_start">Starting Turn</label>
                  <input
                    type="number"
                    id="turn_start"
                    name="turn_start"
                    value={promptForm.turn_start}
                    onChange={handlePromptFormChange}
                    min="0"
                    required
                  />
                </div>
                
                <div className={styles.formGroup}>
                  <label htmlFor="turn_end">Ending Turn (optional)</label>
                  <input
                    type="number"
                    id="turn_end"
                    name="turn_end"
                    value={promptForm.turn_end === null ? '' : promptForm.turn_end}
                    onChange={handlePromptFormChange}
                    min={promptForm.turn_start}
                    placeholder="No end"
                  />
                </div>
              </div>
              
              <div className={styles.formGroup}>
                <label htmlFor="system_prompt">System Prompt</label>
                <textarea
                  id="system_prompt"
                  name="system_prompt"
                  value={promptForm.system_prompt}
                  onChange={handlePromptFormChange}
                  rows="15"
                  required
                />
                <small>
                  You can use variables like {'{current_summary}'}, {'{original_tale_context}'}, etc.
                </small>
              </div>
              
              <div className={styles.formActions}>
                <button 
                  type="button" 
                  className={styles.cancelButton}
                  onClick={() => selectedBaseStory ? setActiveView('editBaseStory') : navigateToMain()}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className={styles.submitButton}
                  disabled={isLoading}
                >
                  Create Prompt
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}