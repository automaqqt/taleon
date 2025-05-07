"use client"

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import styles from '../../styles/Admin.module.css';
import * as authService from '../../services/auth'; // Assuming auth.js is correctly imported

const highlightLogLine = (line) => {
  // Simple replacements for common keywords
  return line
      .replace(/ERROR/g, `<span class="${styles.logHighlightError}">ERROR</span>`)
      .replace(/WARNING/g, `<span class="${styles.logHighlightWarning}">WARNING</span>`)
      .replace(/INFO/g, `<span class="${styles.logHighlightInfo}">INFO</span>`)
      .replace(/DEBUG/g, `<span class="${styles.logHighlightDebug}">DEBUG</span>`);
};

const MAX_LOG_LINES = 1000;

export default function AdminPage() {
  const router = useRouter();

  // --- Authentication State ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminCredentials, setAdminCredentials] = useState(null);

  // --- UI State ---
  // Added storyTypesList, createStoryType, editStoryType views
  const [activeView, setActiveView] = useState('baseStories');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // --- Data State ---
  const [baseStories, setBaseStories] = useState([]);
  const [selectedBaseStory, setSelectedBaseStory] = useState(null);
  const [storyPrompts, setStoryPrompts] = useState([]); // Prompts *assigned* to selected BaseStory/StoryType
  const [storyTypes, setStoryTypes] = useState([]); // NEW: List of all story types
  const [selectedStoryType, setSelectedStoryType] = useState(null); // NEW: For editing
  const [allAvailablePrompts, setAllAvailablePrompts] = useState([]); // NEW: For assignment dropdown
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [logLines, setLogLines] = useState([]); // NEW: For logs
  const [logSearchTerm, setLogSearchTerm] = useState('');

  // --- Form State ---
  const [baseStoryForm, setBaseStoryForm] = useState({
    title: '',
    description: '',
    original_tale_context: '',
    initial_system_prompt: '', // Keep for Turn 0
    initial_summary: '',
    language: 'Deutsch',
    story_type_id: '' // NEW: Link to StoryType
  });

  const [promptForm, setPromptForm] = useState({ // For creating NEW prompts
    name: '',
    system_prompt: '',
    turn_start: 0,
    turn_end: null
    // Removed base_story_id - prompts are linked to StoryType now
  });

  // NEW: Form state for StoryType
  const [storyTypeForm, setStoryTypeForm] = useState({
      name: '',
      description: '',
      initial_extraction_prompt: '',
      dynamic_analysis_prompt: '',
      summary_prompt: ''
  });

  // NEW: State for assigning prompts
  const [promptToAssign, setPromptToAssign] = useState('');

  // --- Authentication & Initial Load ---
  useEffect(() => {
    const user = authService.getCurrentUser();
    const adminCreds = authService.getAdminCredentials();

    if (user && adminCreds && authService.isAdmin()) { // Check isAdmin
      setIsAuthenticated(true);
      setIsAdmin(true);
      setAdminCredentials(adminCreds);
      // Load initial data based on default view
      if (activeView === 'baseStories') {
          loadBaseStories();
          loadStoryTypes(); // Load types for dropdowns later
      } else if (activeView === 'storyTypesList') {
          loadStoryTypes();
      } else if (activeView === 'promptList') { // <-- ADDED
        loadAllPrompts();
     } else if (activeView === 'logs') { loadLogs(); }
    } else {
      router.push('/'); // Redirect if not admin
    }
  }, [router, activeView]); // Re-run if activeView changes to load correct data

  // --- Data Loading Functions ---

  async function loadLogs() {
    if (!adminCredentials) return;
    setIsLoading(true); setError(null);
    try {
        const logData = await authService.adminGetLogs(adminCredentials);
        setLogLines(logData.lines || []); // Ensure it's an array
    } catch (err) {
        setError(`Failed to load logs: ${err.message}`);
        setLogLines([`Error loading logs: ${err.message}`]); // Show error in log view
    } finally {
        setIsLoading(false);
    }
}

  async function loadBaseStories() {
    if (!adminCredentials) return;
    setIsLoading(true); setError(null);
    try {
      const stories = await authService.getBaseStories(); // Assumes this returns enough info
      setBaseStories(stories);
    } catch (err) { setError(`Failed to load base stories: ${err.message}`); }
    finally { setIsLoading(false); }
  }

  async function loadStoryTypes() {
      if (!adminCredentials) return;
      setIsLoading(true); setError(null);
      try {
          // Use the new API function
          const types = await authService.adminGetStoryTypes(adminCredentials);
          setStoryTypes(types);
      } catch (err) {
          setError(`Failed to load story types: ${err.message}`);
      } finally {
          setIsLoading(false);
      }
  }

  async function loadAllPrompts() {
    if (!adminCredentials) return;
    // Avoid reloading if already loaded and not explicitly needed? Optional optimization.
    // if (allAvailablePrompts.length > 0 && !forceReload) return;
    setIsLoading(true); setError(null);
    try {
        const prompts = await authService.adminGetAllStoryPrompts(adminCredentials);
        setAllAvailablePrompts(prompts);
    } catch (err) {
        setError(`Failed to load all prompts: ${err.message}`);
    } finally {
        setIsLoading(false);
    }
}

  async function loadPromptDetails(promptId) {
    if (!adminCredentials) return;
    setIsLoading(true); setError(null);
    try {
        const promptDetails = await authService.adminGetStoryPromptDetails(promptId, adminCredentials);
        setSelectedPrompt(promptDetails); // Store the full prompt being edited

        // Populate the form state
        setPromptForm({
            name: promptDetails.name,
            system_prompt: promptDetails.system_prompt,
            turn_start: promptDetails.turn_start,
            // Handle null correctly when setting the form value
            turn_end: promptDetails.turn_end === null ? '' : promptDetails.turn_end
        });

        setActiveView('editPrompt'); // Switch to the edit view
    } catch (err) {
        setError(`Failed to load prompt details: ${err.message}`);
    } finally {
        setIsLoading(false);
    }
}

const handleLogSearchChange = (e) => {
  setLogSearchTerm(e.target.value);
};

const navigateToLogs = () => {
  setActiveView('logs');
  setLogLines([]); // Clear previous logs
  setLogSearchTerm(''); // Reset search
  // loadLogs will be triggered by useEffect
};

// --- Filtering and Memoization for Logs ---
const filteredLogLines = useMemo(() => {
   if (!logSearchTerm) {
       return logLines; // Return all lines if no search term
   }
   const lowerCaseSearch = logSearchTerm.toLowerCase();
   return logLines.filter(line =>
       line.toLowerCase().includes(lowerCaseSearch)
   );
}, [logLines, logSearchTerm]); // Recalculate only when logs or search term change


async function handleUpdatePrompt(e) {
  e.preventDefault();
  if (!adminCredentials || !selectedPrompt) return;
  setIsLoading(true); setError(null); setSuccessMessage(null);
  const updateData = { /* ... prepare data ... */
      ...promptForm,
      turn_end: promptForm.turn_end === '' ? null : parseInt(promptForm.turn_end, 10)
  };
  try {
      const result = await authService.adminUpdateStoryPrompt(selectedPrompt.id, updateData, adminCredentials); // Ensure correct function name
      if (result) {
          setSuccessMessage(`Successfully updated prompt "${result.name}"!`);
          setTimeout(() => {
              setSuccessMessage(null);
              // Navigate back intelligently
              if (selectedStoryType) { // If editing context was a StoryType
                  loadStoryTypeDetails(selectedStoryType.id);
              } else { // Otherwise, assume we came from the prompt list
                  navigateToPromptList(); // Go back to the prompt list view
              }
          }, 1500);
      } else { setError("Failed to update prompt."); }
  } catch (err) { setError(`Failed to update prompt: ${err.message}`); }
  finally { setIsLoading(false); }
}

const handleDeletePrompt = async (promptId, promptName) => {
  if (!adminCredentials) return;
  // Determine where to navigate back to *before* confirmation potentially clears state
  const cameFromStoryTypeEdit = !!selectedStoryType; // Check if we were editing a story type

  if (window.confirm(`!!! DESTRUCTIVE ACTION !!!\n\nAre you sure you want to permanently delete the PROMPT "${promptName}" (ID: ${promptId})?\n\nThis cannot be undone and will remove it from ALL Story Types it's assigned to.`)) {
      setIsLoading(true); setError(null); setSuccessMessage(null);
      try {
          await authService.adminDeleteStoryPrompt(promptId, adminCredentials);
          setSuccessMessage(`Prompt "${promptName}" deleted successfully.`);

          if (selectedPrompt?.id === promptId) { setSelectedPrompt(null); setPromptForm({ name: '', system_prompt: '', turn_start: 0, turn_end: null }); }

          setTimeout(() => {
              setSuccessMessage(null);
              if (cameFromStoryTypeEdit && selectedStoryType) {
                  // If deleted while editing a story type, reload that type's details
                  loadStoryTypeDetails(selectedStoryType.id);
              } else {
                  // Otherwise (deleted from list or from edit prompt page without story type context), refresh the main prompt list
                  loadAllPrompts(); // Refresh the list data
                  setActiveView('promptList'); // Ensure we are on the list view
              }
          }, 2000);
      } catch (err) {
          setError(`Failed to delete prompt: ${err.message}`);
          setIsLoading(false);
      }
  }
};
  async function loadAllPrompts() {
       if (!adminCredentials) return;
       setIsLoading(true); setError(null);
       try {
           // Use the new API function
           const prompts = await authService.adminGetAllStoryPrompts(adminCredentials);
           setAllAvailablePrompts(prompts);
       } catch (err) {
           setError(`Failed to load all prompts: ${err.message}`);
       } finally {
           setIsLoading(false);
       }
  }


  async function loadBaseStoryDetails(storyId) {
    if (!adminCredentials) return;
    setIsLoading(true); setError(null);
    try {
      // This API might need adjustment on the backend to return story_type_id
      const storyDetails = await authService.adminGetBaseStory(storyId, adminCredentials);
      setSelectedBaseStory(storyDetails);
      // Prompts are now linked to StoryType, so remove prompt loading here
      // setStoryPrompts(storyDetails.story_prompts || []); // REMOVE THIS

      setBaseStoryForm({
        title: storyDetails.title,
        description: storyDetails.description,
        original_tale_context: storyDetails.original_tale_context,
        initial_system_prompt: storyDetails.initial_system_prompt,
        initial_summary: storyDetails.initial_summary,
        language: storyDetails.language || 'Deutsch',
        story_type_id: storyDetails.story_type_id || '' // Load story type ID
      });
      await loadStoryTypes(); // Ensure types are loaded for the dropdown
      setActiveView('editBaseStory');
    } catch (err) { setError(`Failed to load base story details: ${err.message}`); }
    finally { setIsLoading(false); }
  }

  // NEW: Load Story Type Details
  async function loadStoryTypeDetails(storyTypeId) {
      if (!adminCredentials) return;
      setIsLoading(true); setError(null);
      try {
          const typeDetails = await authService.adminGetStoryTypeDetails(storyTypeId, adminCredentials);
          setSelectedStoryType(typeDetails);
          setStoryPrompts(typeDetails.story_prompts || []); // Load assigned prompts

          setStoryTypeForm({
              name: typeDetails.name,
              description: typeDetails.description || '',
              initial_extraction_prompt: typeDetails.initial_extraction_prompt,
              dynamic_analysis_prompt: typeDetails.dynamic_analysis_prompt,
              summary_prompt: typeDetails.summary_prompt
          });
          await loadAllPrompts(); // Load all prompts for assignment dropdown
          setActiveView('editStoryType');
      } catch (err) {
          setError(`Failed to load story type details: ${err.message}`);
      } finally {
          setIsLoading(false);
      }
  }

  // --- Form Submission Handlers ---

  async function handleCreateBaseStory(e) {
    e.preventDefault();
    if (!adminCredentials || !baseStoryForm.story_type_id) {
        setError("Please select a Story Type.");
        return;
    }
    setIsLoading(true); setError(null); setSuccessMessage(null);
    try {
      // Pass the full form state, including story_type_id
      const result = await authService.adminCreateBaseStory(baseStoryForm, adminCredentials);

      if (result && result.success) {
        setSuccessMessage(`Successfully created "${result.title}" base story!`);
        setBaseStoryForm({ title: '', description: '', original_tale_context: '', initial_system_prompt: '', initial_summary: '', language: 'Deutsch', story_type_id: '' });
        setTimeout(() => { loadBaseStories(); setActiveView('baseStories'); setSuccessMessage(null); }, 1500);
      } else {
         setError("Failed to create base story. Response indicates failure.");
      }
    } catch (err) { setError(`Failed to create base story: ${err.message}`); }
    finally { setIsLoading(false); }
  }

  async function handleUpdateBaseStory(e) {
    e.preventDefault();
    if (!adminCredentials || !selectedBaseStory || !baseStoryForm.story_type_id) {
         setError("Please select a Story Type.");
         return;
    }
    setIsLoading(true); setError(null); setSuccessMessage(null);
    try {
      // Pass the full form state, including story_type_id
      const result = await authService.adminUpdateBaseStory(selectedBaseStory.id, baseStoryForm, adminCredentials);
      if (result.title) {
        setSuccessMessage(`Successfully updated "${result.title}" base story!`);
        setTimeout(() => { loadBaseStories(); setActiveView('baseStories'); setSuccessMessage(null); }, 1500);
      } else {
         setError("Failed to update base story. Response indicates failure.");
      }
    } catch (err) { setError(`Failed to update base story: ${err.message}`); }
    finally { setIsLoading(false); }
  }

  // REVISED: Create Prompt (now standalone, not linked immediately)
  async function handleCreatePrompt(e) {
    e.preventDefault();
    if (!adminCredentials) return;
    setIsLoading(true); setError(null); setSuccessMessage(null);
    try {
        // Create the prompt without assigning it here
        const result = await authService.adminCreateStoryPrompt(promptForm, adminCredentials);
        console.log(result)
        if (result.name) {
            setSuccessMessage(`Successfully created "${result.name}" prompt! It can now be assigned to a Story Type.`);
            setPromptForm({ name: '', system_prompt: '', turn_start: 0, turn_end: null });
            // Optionally navigate back or reload prompt list if staying on a prompt management view
            setTimeout(() => {
                // If we came from editStoryType, go back there
                if(activeView === 'createPrompt' && selectedStoryType) {
                    loadStoryTypeDetails(selectedStoryType.id); // Reload details which includes prompts
                } else {
                    // Otherwise, maybe go to a general prompt list or back to main
                     setActiveView('baseStories'); // Or a new dedicated prompt view
                }
                 setSuccessMessage(null);
            }, 2000);
        } else {
            setError("Failed to create prompt. Response indicates failure.");
        }
    } catch (err) { setError(`Failed to create prompt: ${err.message}`); }
    finally { setIsLoading(false); }
}

  // NEW: Create Story Type
  async function handleCreateStoryType(e) {
      e.preventDefault();
      if (!adminCredentials) return;
      setIsLoading(true); setError(null); setSuccessMessage(null);
      try {
          const result = await authService.adminCreateStoryType(storyTypeForm, adminCredentials);
          console.log(result)
          if (result.name) {
              setSuccessMessage(`Successfully created "${result.name}" story type!`);
              setStoryTypeForm({ name: '', description: '', initial_extraction_prompt: '', dynamic_analysis_prompt: '', summary_prompt: '' });
              setTimeout(() => { loadStoryTypes(); setActiveView('storyTypesList'); setSuccessMessage(null); }, 1500);
          } else {
             setError("Failed to create story type. Response indicates failure.");
          }
      } catch (err) {
          setError(`Failed to create story type: ${err.message}`);
      } finally {
          setIsLoading(false);
      }
  }

  // NEW: Update Story Type
  async function handleUpdateStoryType(e) {
      e.preventDefault();
      if (!adminCredentials || !selectedStoryType) return;
      setIsLoading(true); setError(null); setSuccessMessage(null);
      try {
          const result = await authService.adminUpdateStoryType(selectedStoryType.id, storyTypeForm, adminCredentials);
          if (result.name) {
              setSuccessMessage(`Successfully updated "${result.name}" story type!`);
              setTimeout(() => { loadStoryTypes(); setActiveView('storyTypesList'); setSuccessMessage(null); }, 1500);
          } else {
             setError("Failed to update story type. Response indicates failure.");
          }
      } catch (err) {
          setError(`Failed to update story type: ${err.message}`);
      } finally {
          setIsLoading(false);
      }
  }


  // --- Deletion Handlers ---

  // handleDeleteBaseStory (No changes needed in logic, just UI context)
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
    }};
    

  // NEW: Delete Story Type
  const handleDeleteStoryType = async (typeId, typeName) => {
      if (!adminCredentials || !typeId) return;
      if (window.confirm(`!!! DESTRUCTIVE ACTION !!!\n\nAre you sure you want to permanently delete the Story Type "${typeName}" (ID: ${typeId})?\n\nThis cannot be undone and will fail if any Base Stories use this type.`)) {
          setIsLoading(true); setError(null); setSuccessMessage(null);
          try {
              await authService.adminDeleteStoryType(typeId, adminCredentials);
              setSuccessMessage(`Story Type "${typeName}" deleted successfully.`);
              setTimeout(() => {
                  setSuccessMessage(null);
                  navigateToStoryTypes(); // Go back to the list view
              }, 2000);
          } catch (err) {
              setError(`Failed to delete story type: ${err.message}`);
              setIsLoading(false);
          }
      }
  };

  // --- Prompt Assignment Handlers ---

  const handleAssignPrompt = async (e) => {
       e.preventDefault();
       if (!adminCredentials || !selectedStoryType || !promptToAssign) {
           setError("Please select a prompt to assign.");
           return;
       }
       setIsLoading(true); setError(null); setSuccessMessage(null);
       try {
           await authService.adminAssignPromptToStoryType(promptToAssign, selectedStoryType.id, adminCredentials);
           setSuccessMessage("Prompt assigned successfully!");
           setPromptToAssign(''); // Reset dropdown
           await loadStoryTypeDetails(selectedStoryType.id); // Reload details
           setTimeout(() => setSuccessMessage(null), 2000);
       } catch (err) {
           setError(`Failed to assign prompt: ${err.message}`);
       } finally {
           setIsLoading(false);
       }
  };

  const handleRemovePromptFromType = async (promptId, promptName) => {
       if (!adminCredentials || !selectedStoryType) return;
       if (window.confirm(`Are you sure you want to remove the prompt "${promptName}" from the Story Type "${selectedStoryType.name}"? The prompt itself will not be deleted.`)) {
           setIsLoading(true); setError(null); setSuccessMessage(null);
           try {
               await authService.adminRemovePromptFromStoryType(promptId, selectedStoryType.id, adminCredentials);
               setSuccessMessage(`Prompt "${promptName}" removed from this story type.`);
               await loadStoryTypeDetails(selectedStoryType.id); // Reload details
               setTimeout(() => setSuccessMessage(null), 2000);
           } catch (err) {
               setError(`Failed to remove prompt assignment: ${err.message}`);
           } finally {
               setIsLoading(false);
           }
       }
  };


  // --- Form Change Handlers ---
  const handleBaseStoryFormChange = (e) => {
    const { name, value } = e.target;
    setBaseStoryForm(prev => ({ ...prev, [name]: value }));
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
  // NEW: Story Type Form Change
  const handleStoryTypeFormChange = (e) => {
      const { name, value } = e.target;
      setStoryTypeForm(prev => ({ ...prev, [name]: value }));
  };

  // --- UI Navigation Handlers ---
  const navigateToMain = () => { setActiveView('baseStories'); setSelectedBaseStory(null); setSelectedStoryType(null); loadBaseStories(); };
  const navigateToCreateBaseStory = () => {
      setBaseStoryForm({ title: '', description: '', original_tale_context: '', initial_system_prompt: '', initial_summary: '', language: 'Deutsch', story_type_id: '' });
      loadStoryTypes(); // Load types for dropdown
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
  // NEW Navigation
  const navigateToStoryTypes = () => { setActiveView('storyTypesList'); setSelectedStoryType(null); setSelectedBaseStory(null); loadStoryTypes(); };
  const navigateToCreateStoryType = () => {
      setStoryTypeForm({ name: '', description: '', initial_extraction_prompt: '', dynamic_analysis_prompt: '', summary_prompt: '' });
      setActiveView('createStoryType');
  };

  const navigateToPromptList = () => {
    setActiveView('promptList');
    setSelectedPrompt(null); // Clear selection when going to the list
    setSelectedStoryType(null); // Clear story type context
    setSelectedBaseStory(null); // Clear base story context
    loadAllPrompts(); // Load/refresh the list
};

  // --- Render Logic ---
  if (!isAuthenticated || !isAdmin) {
    return <div className={styles.loading}>Checking credentials...</div>;
  }

  // Filter for assignable prompts (all prompts minus already assigned ones)
  const assignablePrompts = allAvailablePrompts.filter(
       p => !storyPrompts.some(assigned => assigned.id === p.id)
  );

  return (
    <div className={styles.adminContainer}>
      <header className={styles.adminHeader}>
        <h1>Taleon Admin Panel</h1>
        <div className={styles.adminNav}>
          {/* Base Story Nav */}
          <button className={`${styles.navButton} ${activeView === 'baseStories' ? styles.active : ''}`} onClick={navigateToMain}>Base Stories</button>
          
          {/* Story Type Nav */}
          <button className={`${styles.navButton} ${activeView === 'storyTypesList' ? styles.active : ''}`} onClick={navigateToStoryTypes}>Story Types</button>
          {/* Prompt Nav */}
          <button className={`${styles.navButton} ${activeView === 'promptList' ? styles.active : ''}`} onClick={navigateToPromptList}>Manage Prompts</button> {/* Renamed */}
          <button className={`${styles.navButton} ${activeView === 'logs' ? styles.active : ''}`} onClick={navigateToLogs}>View Logs</button>
          {/* Logout */}
          <button className={styles.logoutButton} onClick={() => { authService.logout(); router.push('/'); }}>Logout</button>
        </div>
      </header>

      {/* Conditional rendering OUTSIDE adminMain for logs */}
      {activeView === 'logs' && (
          <div className={styles.logViewFullWidthWrapper}> {/* Optional wrapper */}
              {/* Loading/Error/Success Messages can be here or inside */}
              {isLoading && <div className={styles.loading}>Loading...</div>}
              {error && <div className={styles.errorMessage}><p>{error}</p><button onClick={() => setError(null)}>Dismiss</button></div>}
              {successMessage && <div className={styles.successMessage}><p>{successMessage}</p></div>}

              <div className={styles.logViewContainer}>
              <h2>Application Logs</h2>
                <p><small>Showing last {logLines.length} lines (max {MAX_LOG_LINES}) from output.log. Filtering is case-insensitive.</small></p>

                <div className={styles.logSearchContainer}>
                    <input
                        type="text"
                        placeholder="Search logs..."
                        value={logSearchTerm}
                        onChange={handleLogSearchChange}
                        className={styles.logSearchInput}
                    />
                     <button onClick={loadLogs} disabled={isLoading} className={styles.refreshLogButton}>
                        Refresh Logs
                    </button>
                </div>

                <div className={styles.logDisplayArea}>
                    {filteredLogLines.length > 0 ? (
                        filteredLogLines.map((line, index) => (
                            <pre
                                key={index}
                                className={styles.logLine}
                                // Use dangerouslySetInnerHTML for basic HTML highlighting
                                // Be cautious if log content could ever contain untrusted HTML
                                dangerouslySetInnerHTML={{ __html: highlightLogLine(line) }}
                            />
                        ))
                    ) : (
                        <p className={styles.noLogsMessage}>
                            {logSearchTerm ? 'No log lines match your search term.' : 'No log lines loaded or log file is empty.'}
                        </p>
                    )}
                </div>
              </div>
          </div>
      )}

      <main className={styles.adminMain}>
        {/* Loading/Error/Success Messages */}
        {isLoading && <div className={styles.loading}>Loading...</div>}
        {error && <div className={styles.errorMessage}><p>{error}</p><button onClick={() => setError(null)}>Dismiss</button></div>}
        {successMessage && <div className={styles.successMessage}><p>{successMessage}</p></div>}

        {/* --- VIEW: Base Stories List --- */}
        {activeView === 'baseStories' && (
             <div className={styles.baseStoriesList}>
                 <h2>Available Base Stories</h2>
                 {/* ... (existing map logic for baseStories) ... */}
                 {baseStories.length === 0 ? <p>No base stories found.</p> : (
                     <div className={styles.storiesGrid}>
                       {baseStories.map(story => (
                         <div key={story.id} className={styles.storyCard}>
                           <h3>{story.title}</h3>
                           <p>{story.description}</p>
                           {/* Display Story Type Name if available */}
                           <p className={styles.storyMeta}>Type: {story.storyTypeName || 'N/A'}</p>
                           <p className={styles.storyMeta}>Language: {story.language} <span className={`${styles.activeStatus} ${story.is_active ? styles.active : styles.inactive}`}>{story.is_active ? 'Active' : 'Inactive'}</span></p>
                           <div className={styles.storyActions}>
                             <button className={styles.editButton} onClick={() => loadBaseStoryDetails(story.id)}>Edit</button>
                             {/* ... other buttons like toggle active ... */}
                           </div>
                         </div>
                       ))}
                     </div>
                 )}
                 <button className={styles.submitButton} style={{marginTop: '20px'}} onClick={navigateToCreateBaseStory}>Create Base Story</button>
             </div>
             
         )}

        {/* --- VIEW: Create Base Story --- */}
        {activeView === 'createBaseStory' && (
          <div className={styles.formContainer}>
            <h2>Create New Base Story</h2>
            <form onSubmit={handleCreateBaseStory}>
              {/* ... (fields for title, language, description, original_tale_context, initial_summary, initial_system_prompt) ... */}
               <div className={styles.formGroup}>
                 <label htmlFor="title">Title</label>
                 <input type="text" id="title" name="title" value={baseStoryForm.title} onChange={handleBaseStoryFormChange} required />
               </div>
                <div className={styles.formGroup}>
                   <label htmlFor="story_type_id">Story Type *</label>
                   <select id="story_type_id" name="story_type_id" value={baseStoryForm.story_type_id} onChange={handleBaseStoryFormChange} required >
                       <option value="" disabled>-- Select a Story Type --</option>
                       {storyTypes.map(type => (
                           <option key={type.id} value={type.id}>{type.name}</option>
                       ))}
                   </select>
                   {storyTypes.length === 0 && <small>No story types found. Please create one first.</small>}
               </div>
               <div className={styles.formGroup}>
                  <label htmlFor="language">Language</label>
                  <select id="language" name="language" value={baseStoryForm.language} onChange={handleBaseStoryFormChange}>
                     <option value="Deutsch">German</option>
                     {/* ... other languages ... */}
                  </select>
               </div>
               <div className={styles.formGroup}>
                  <label htmlFor="description">Description</label>
                  <textarea id="description" name="description" value={baseStoryForm.description} onChange={handleBaseStoryFormChange} rows="3" required />
               </div>
               <div className={styles.formGroup}>
                   <label htmlFor="original_tale_context">Original Tale Context / World Description</label>
                   <textarea id="original_tale_context" name="original_tale_context" value={baseStoryForm.original_tale_context} onChange={handleBaseStoryFormChange} rows="5" required />
                   <small>The core text used for initial element extraction based on the selected Story Type.</small>
               </div>
                <div className={styles.formGroup}>
                   <label htmlFor="initial_system_prompt">Initial System Prompt (Turn 0)</label>
                   <textarea id="initial_system_prompt" name="initial_system_prompt" value={baseStoryForm.initial_system_prompt} onChange={handleBaseStoryFormChange} rows="5" required />
                   <small>The very first prompt used when a user starts this story.</small>
               </div>
               <div className={styles.formGroup}>
                  <label htmlFor="initial_summary">Starting Summary</label>
                  <textarea id="initial_summary" name="initial_summary" value={baseStoryForm.initial_summary} onChange={handleBaseStoryFormChange} rows="3" required />
                  <small>The initial summary presented to the user.</small>
               </div>

              <div className={styles.formActions}>
                <button type="button" className={styles.cancelButton} onClick={navigateToMain}>Cancel</button>
                <button type="submit" className={styles.submitButton} disabled={isLoading || storyTypes.length === 0}>Create Base Story</button>
              </div>
            </form>
          </div>
        )}

        {/* --- VIEW: Edit Base Story --- */}
        {activeView === 'editBaseStory' && selectedBaseStory && (
          <div className={styles.formContainer}>
            <h2>Edit Base Story: {selectedBaseStory.title}</h2>
            <form onSubmit={handleUpdateBaseStory}>
              {/* ... (fields for title, language, description, original_tale_context, initial_summary, initial_system_prompt) ... */}
              {/* Make sure to include the Story Type dropdown here too */}
               <div className={styles.formGroup}>
                 <label htmlFor="title">Title</label>
                 <input type="text" id="title" name="title" value={baseStoryForm.title} onChange={handleBaseStoryFormChange} required />
               </div>
               <div className={styles.formGroup}>
                   <label htmlFor="story_type_id">Story Type *</label>
                   <select id="story_type_id" name="story_type_id" value={baseStoryForm.story_type_id} onChange={handleBaseStoryFormChange} required >
                       <option value="" disabled>-- Select a Story Type --</option>
                       {storyTypes.map(type => (
                           <option key={type.id} value={type.id}>{type.name}</option>
                       ))}
                   </select>
               </div>
              {/* ... other fields identical to create view ... */}
               <div className={styles.formGroup}>
                  <label htmlFor="language">Language</label> {/* Example */}
                  <select id="language" name="language" value={baseStoryForm.language} onChange={handleBaseStoryFormChange}> <option value="Deutsch">German</option> </select>
               </div>
               <div className={styles.formGroup}>
                  <label htmlFor="description">Description</label> {/* Example */}
                  <textarea id="description" name="description" value={baseStoryForm.description} onChange={handleBaseStoryFormChange} rows="3" required />
               </div>
               <div className={styles.formGroup}>
                   <label htmlFor="original_tale_context">Original Tale Context / World Description</label> {/* Example */}
                   <textarea id="original_tale_context" name="original_tale_context" value={baseStoryForm.original_tale_context} onChange={handleBaseStoryFormChange} rows="5" required />
               </div>
                <div className={styles.formGroup}>
                   <label htmlFor="initial_system_prompt">Initial System Prompt (Turn 0)</label> {/* Example */}
                   <textarea id="initial_system_prompt" name="initial_system_prompt" value={baseStoryForm.initial_system_prompt} onChange={handleBaseStoryFormChange} rows="5" required />
               </div>
               <div className={styles.formGroup}>
                  <label htmlFor="initial_summary">Starting Summary</label> {/* Example */}
                  <textarea id="initial_summary" name="initial_summary" value={baseStoryForm.initial_summary} onChange={handleBaseStoryFormChange} rows="3" required />
               </div>


              <div className={styles.formActions}>
                <button type="button" className={styles.cancelButton} onClick={navigateToMain}>Cancel</button>
                <button type="submit" className={styles.submitButton} disabled={isLoading}>Update Base Story</button>
              </div>
            </form>

            {/* Display Initial Elements */}
            {selectedBaseStory.initial_story_elements && Object.keys(selectedBaseStory.initial_story_elements).length > 0 ? (
              <div className={styles.initialElementsSection}>
                <h4>Initial Story Elements (Auto-Extracted via Story Type)</h4>
                <pre className={styles.jsonDisplay}>{JSON.stringify(selectedBaseStory.initial_story_elements, null, 2)}</pre>
              </div>
            ) : ( <div className={styles.initialElementsSection}><p>No initial elements stored.</p></div> )}

            {/* REMOVED prompts section - managed under StoryType now */}

            {/* Delete Base Story Section */}
            <div className={styles.deleteSection}>
               {/* ... (keep existing delete button) ... */}
                <h3>Delete Base Story</h3>
                <p className={styles.warningText}>Warning: Deleting a base story is permanent...</p>
                <button onClick={() => handleDeleteBaseStory(selectedBaseStory.id, selectedBaseStory.title)} className={styles.deleteButtonLarge} disabled={isLoading}> Delete "{selectedBaseStory.title}" Base Story </button>
            </div>
          </div>
        )}

        {/* --- VIEW: Story Types List --- */}
        {activeView === 'storyTypesList' && (
            <div className={styles.storyTypesList}>
                <h2>Available Story Types</h2>
                {storyTypes.length === 0 ? <p>No story types found. Create one to get started!</p> : (
                    <div className={styles.storiesGrid}> {/* Reuse grid style */}
                        {storyTypes.map(type => (
                            <div key={type.id} className={styles.storyCard}> {/* Reuse card style */}
                                <h3>{type.name}</h3>
                                <p>{type.description || 'No description'}</p>
                                <div className={styles.storyActions}>
                                    <button className={styles.editButton} onClick={() => loadStoryTypeDetails(type.id)}>Edit / Manage Prompts</button>
                                    <button className={styles.deleteButtonSmall} onClick={() => handleDeleteStoryType(type.id, type.name)} disabled={isLoading}>Delete Type</button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                 <button className={styles.submitButton} style={{marginTop: '20px'}} onClick={navigateToCreateStoryType}>Create New Story Type</button>
            </div>
        )}

        {/* --- VIEW: Create Story Type --- */}
        {activeView === 'createStoryType' && (
             <div className={styles.formContainer}>
                <h2>Create New Story Type</h2>
                <form onSubmit={handleCreateStoryType}>
                    <div className={styles.formGroup}>
                        <label htmlFor="name">Name *</label>
                        <input type="text" id="name" name="name" value={storyTypeForm.name} onChange={handleStoryTypeFormChange} required />
                    </div>
                    <div className={styles.formGroup}>
                        <label htmlFor="description">Description</label>
                        <textarea id="description" name="description" value={storyTypeForm.description} onChange={handleStoryTypeFormChange} rows="3" />
                    </div>
                    <div className={styles.formGroup}>
                        <label htmlFor="initial_extraction_prompt">Initial Extraction Prompt *</label>
                        <textarea id="initial_extraction_prompt" name="initial_extraction_prompt" value={storyTypeForm.initial_extraction_prompt} onChange={handleStoryTypeFormChange} rows="8" required />
                        <small>Used once when creating a Base Story of this type to analyze its 'Original Tale Context'. Should output JSON.</small>
                    </div>
                    <div className={styles.formGroup}>
                        <label htmlFor="dynamic_analysis_prompt">Dynamic Analysis Prompt *</label>
                        <textarea id="dynamic_analysis_prompt" name="dynamic_analysis_prompt" value={storyTypeForm.dynamic_analysis_prompt} onChange={handleStoryTypeFormChange} rows="8" required />
                        <small>Used periodically during a story to analyze recent events and update context. Compares against existing context, outputs JSON of changes.</small>
                    </div>
                    <div className={styles.formGroup}>
                        <label htmlFor="summary_prompt">Summary Prompt *</label>
                        <textarea id="summary_prompt" name="summary_prompt" value={storyTypeForm.summary_prompt} onChange={handleStoryTypeFormChange} rows="8" required />
                        <small>Used periodically to generate the story's running summary based on existing summary and recent events.</small>
                    </div>
                    <div className={styles.formActions}>
                        <button type="button" className={styles.cancelButton} onClick={navigateToStoryTypes}>Cancel</button>
                        <button type="submit" className={styles.submitButton} disabled={isLoading}>Create Story Type</button>
                    </div>
                </form>
             </div>
        )}

        {/* --- VIEW: Edit Story Type --- */}
        {activeView === 'editStoryType' && selectedStoryType && (
            <div className={styles.formContainer}>
               <h2>Edit Story Type: {selectedStoryType.name}</h2>
               <form onSubmit={handleUpdateStoryType}>
                   {/* Fields identical to create view */}
                    <div className={styles.formGroup}><label htmlFor="name">Name *</label><input type="text" id="name" name="name" value={storyTypeForm.name} onChange={handleStoryTypeFormChange} required /></div>
                    <div className={styles.formGroup}><label htmlFor="description">Description</label><textarea id="description" name="description" value={storyTypeForm.description} onChange={handleStoryTypeFormChange} rows="3" /></div>
                    <div className={styles.formGroup}><label htmlFor="initial_extraction_prompt">Initial Extraction Prompt *</label><textarea id="initial_extraction_prompt" name="initial_extraction_prompt" value={storyTypeForm.initial_extraction_prompt} onChange={handleStoryTypeFormChange} rows="8" required /></div>
                    <div className={styles.formGroup}><label htmlFor="dynamic_analysis_prompt">Dynamic Analysis Prompt *</label><textarea id="dynamic_analysis_prompt" name="dynamic_analysis_prompt" value={storyTypeForm.dynamic_analysis_prompt} onChange={handleStoryTypeFormChange} rows="8" required /></div>
                    <div className={styles.formGroup}><label htmlFor="summary_prompt">Summary Prompt *</label><textarea id="summary_prompt" name="summary_prompt" value={storyTypeForm.summary_prompt} onChange={handleStoryTypeFormChange} rows="8" required /></div>

                   <div className={styles.formActions}>
                       <button type="button" className={styles.cancelButton} onClick={navigateToStoryTypes}>Cancel</button>
                       <button type="submit" className={styles.submitButton} disabled={isLoading}>Update Story Type</button>
                   </div>
               </form>

               {/* --- Assigned Prompts Section --- */}
               {/* --- Assigned Prompts Section --- */}
               <div className={styles.promptsSection}>
                   <h3>Assigned Story Prompts</h3>
                   {storyPrompts && storyPrompts.length > 0 ? (
                       <div className={styles.promptsList}>
                           {storyPrompts.map(prompt => (
                               <div key={prompt.id} className={styles.promptItem}>
                                   <div className={styles.promptHeader}>
                                      <h4>{prompt.name}</h4>
                                      {/* Action Buttons for each prompt */}
                                      <div className={styles.promptItemActions}>
                                          <button
                                              onClick={() => loadPromptDetails(prompt.id)} // <-- EDIT BUTTON
                                              className={styles.editButton} // Reuse edit button style
                                              style={{marginRight: '0.5rem'}} // Add some margin
                                              disabled={isLoading}
                                          >
                                              Edit
                                          </button>
                                          <button
                                              onClick={() => handleRemovePromptFromType(prompt.id, prompt.name)}
                                              className={styles.deleteButtonSmall} // Reuse delete style
                                              title="Remove from this Story Type"
                                              disabled={isLoading}
                                          >
                                              Remove
                                          </button>
                                      </div>
                                   </div>
                                   <p>Turns: {prompt.turn_start} - {prompt.turn_end ?? 'End'}</p>
                               </div>
                           ))}
                       </div>
                   ) : (<p>No prompts assigned to this story type yet.</p>)}

                   {/* --- Assign Prompt Form --- */}
                   <form onSubmit={handleAssignPrompt} className={styles.assignPromptForm}>
                       <h4>Assign Existing Prompt</h4>
                       <div className={styles.formRow}>
                          <select value={promptToAssign} onChange={(e) => setPromptToAssign(e.target.value)} required disabled={assignablePrompts.length === 0}>
                               <option value="" disabled>-- Select Prompt to Assign --</option>
                               {assignablePrompts.map(p => (
                                   <option key={p.id} value={p.id}>{p.name} (Turns: {p.turn_start}-{p.turn_end ?? 'End'})</option>
                               ))}
                           </select>
                           <button type="submit" className={styles.assignButton} disabled={isLoading || !promptToAssign || assignablePrompts.length === 0}>Assign</button>
                       </div>
                       {allAvailablePrompts.length === 0 && <small>No prompts available. Create one first.</small>}
                       {allAvailablePrompts.length > 0 && assignablePrompts.length === 0 && <small>All available prompts are already assigned.</small>}
                   </form>
                    <button className={styles.addPromptButton} onClick={navigateToCreatePrompt} disabled={isLoading}>Create New Prompt</button>
               </div>

               {/* Delete Story Type Section */}
               <div className={styles.deleteSection}>
                  <h3>Delete Story Type</h3>
                  <p className={styles.warningText}>Warning: Deleting a story type is permanent...</p>
                  <button onClick={() => handleDeleteStoryType(selectedStoryType.id, selectedStoryType.name)} className={styles.deleteButtonLarge} disabled={isLoading}> Delete "{selectedStoryType.name}" Story Type </button>
               </div>
            </div>
        )}

       {/* --- VIEW: Create Prompt --- */}
       {activeView === 'createPrompt' && (
            <div className={styles.formContainer}>
                <h2>Create New Story Prompt</h2>
                {/* The form here is reused for the edit view */}
                <form onSubmit={handleCreatePrompt}>
                   <div className={styles.formGroup}><label htmlFor="prompt_name">Prompt Name *</label><input type="text" id="prompt_name" name="name" value={promptForm.name} onChange={handlePromptFormChange} required /></div>
                    <div className={styles.formRow}>
                      <div className={styles.formGroup}><label htmlFor="prompt_turn_start">Starting Turn *</label><input type="number" id="prompt_turn_start" name="turn_start" value={promptForm.turn_start} onChange={handlePromptFormChange} min="0" required /></div>
                      <div className={styles.formGroup}><label htmlFor="prompt_turn_end">Ending Turn (optional)</label><input type="number" id="prompt_turn_end" name="turn_end" value={promptForm.turn_end === null ? '' : promptForm.turn_end} onChange={handlePromptFormChange} min={promptForm.turn_start >= 0 ? promptForm.turn_start : 0} placeholder="No end" /></div>
                    </div>
                    <div className={styles.formGroup}><label htmlFor="prompt_system_prompt">System Prompt *</label><textarea id="prompt_system_prompt" name="system_prompt" value={promptForm.system_prompt} onChange={handlePromptFormChange} rows="15" required /></div>
                    <div className={styles.formActions}>
                       <button type="button" className={styles.cancelButton} onClick={() => selectedStoryType ? setActiveView('editStoryType') : navigateToStoryTypes()}>Cancel</button>
                       <button type="submit" className={styles.submitButton} disabled={isLoading}>Create Prompt</button>
                    </div>
                </form>
            </div>
        )}

        {/* --- NEW VIEW: Prompt List --- */}
        {activeView === 'promptList' && (
            <div className={styles.promptListView}> {/* Optional specific class */}
                <h2>Available Story Prompts</h2>
                {allAvailablePrompts.length === 0 && !isLoading ? (
                    <p>No story prompts found. Create one to get started!</p>
                ) : (
                    <div className={styles.storiesGrid}> {/* Reuse grid style */}
                        {allAvailablePrompts.map(prompt => (
                            <div key={prompt.id} className={styles.storyCard}> {/* Reuse card style */}
                                <h3>{prompt.name}</h3>
                                <p>Turns: {prompt.turn_start} - {prompt.turn_end ?? 'End'}</p>
                                {/* Maybe show snippet of prompt text? Optional */}
                                {/* <details><summary>View Prompt Text</summary><pre className={styles.promptTextDisplay}>{prompt.system_prompt}</pre></details> */}
                                <div className={styles.storyActions}>
                                    <button
                                        className={styles.editButton}
                                        onClick={() => loadPromptDetails(prompt.id)}
                                        disabled={isLoading}
                                    >
                                        Edit
                                    </button>
                                    <button
                                        className={styles.deleteButtonSmall} // Use small delete style
                                        onClick={() => handleDeletePrompt(prompt.id, prompt.name)}
                                        disabled={isLoading}
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                 <button className={styles.submitButton} style={{marginTop: '20px'}} onClick={navigateToCreatePrompt}>Create New Prompt</button>
            </div>
        )}

        {/* --- NEW VIEW: Edit Prompt --- */}
        {activeView === 'editPrompt' && selectedPrompt && (
            <div className={styles.formContainer}>
                <h2>Edit Story Prompt: {selectedPrompt.name}</h2>
                {/* Reuses the same form structure and state as Create Prompt */}
                <form onSubmit={handleUpdatePrompt}> {/* Calls handleUpdatePrompt */}
                   <div className={styles.formGroup}><label htmlFor="prompt_name">Prompt Name *</label><input type="text" id="prompt_name" name="name" value={promptForm.name} onChange={handlePromptFormChange} required /></div>
                    <div className={styles.formRow}>
                      <div className={styles.formGroup}><label htmlFor="prompt_turn_start">Starting Turn *</label><input type="number" id="prompt_turn_start" name="turn_start" value={promptForm.turn_start} onChange={handlePromptFormChange} min="0" required /></div>
                      <div className={styles.formGroup}><label htmlFor="prompt_turn_end">Ending Turn (optional)</label><input type="number" id="prompt_turn_end" name="turn_end" value={promptForm.turn_end === null ? '' : promptForm.turn_end} onChange={handlePromptFormChange} min={promptForm.turn_start >= 0 ? promptForm.turn_start : 0} placeholder="No end" /></div>
                    </div>
                    <div className={styles.formGroup}><label htmlFor="prompt_system_prompt">System Prompt *</label><textarea id="prompt_system_prompt" name="system_prompt" value={promptForm.system_prompt} onChange={handlePromptFormChange} rows="15" required /></div>
                    <div className={styles.formActions}>
                       {/* Navigate back intelligently */}
                       <button type="button" className={styles.cancelButton} onClick={() => selectedStoryType ? setActiveView('editStoryType') : navigateToStoryTypes()}>Cancel</button>
                       <button type="submit" className={styles.submitButton} disabled={isLoading}>Update Prompt</button>
                       {/* Optional: Add Delete button here too */}
                        <button
                            type="button"
                            onClick={() => handleDeletePrompt(selectedPrompt.id, selectedPrompt.name)}
                            className={styles.deleteButtonSmall} // Reuse style or create new
                            style={{marginLeft: 'auto'}} // Push delete to the left
                            disabled={isLoading}
                        >
                            Delete This Prompt
                        </button>
                    </div>
                </form>
            </div>
        )}

      </main>
    </div>
  );
}