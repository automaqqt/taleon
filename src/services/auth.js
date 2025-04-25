// Define backend URL (use environment variable in real app)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

/**
 * Helper function to make API calls
 * @param {string} endpoint - API endpoint
 * @param {string} method - HTTP method (GET, POST, etc)
 * @param {object} data - Data to send in the request body
 * @returns {Promise} Promise that resolves to the API response
 */
async function apiCall(endpoint, method = 'GET', data = null) {
  const url = `${API_BASE_URL}${endpoint}`;

  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    // Removed credentials: 'include' as it's often not needed when passing auth in body,
    // but keep it if your backend specifically requires cookies AND body auth.
    // credentials: 'include',
  };

  // Modify how auth is handled in API calls for admin routes specifically
  // Check if data contains an 'auth' key, which indicates an admin request needing credentials
  if (data && data.auth) {
    // Assuming the backend expects username/password directly in the auth object
    //const authCredentials = data.auth; // Extract the credentials object
    const requestData = { ...data }; // Clone data
    delete requestData.auth; // Remove the auth object itself if it only contains credentials

    // Add credentials directly or nested as needed by the backend API structure
    // Example: nesting under 'auth' key
    //requestData.auth = authCredentials;

    // Example: adding directly to the root (less common for credentials)
    // requestData.username = authCredentials.username;
    // requestData.password = authCredentials.password;

    options.body = JSON.stringify(requestData);

  } else if (data) {
    options.body = JSON.stringify(data);
  }


  try {
    const response = await fetch(url, options);

    // Check if response is OK
    if (!response.ok) {
      let errorMessage = `API Error: ${response.status} ${response.statusText}`;

      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch (e) {
        console.error(`JSON handling erro: ${e}`);
      }

      throw new Error(errorMessage);
    }

    // Handle empty response body for methods like PUT/DELETE that might return 204 No Content
     if (response.status === 204 || response.headers.get('content-length') === '0') {
        return { success: true }; // Or return null, or an appropriate success object
    }


    return await response.json();
  } catch (error) {
    console.error(`API call failed: ${method} ${endpoint} - ${error.message}`);
    throw error;
  }
}

/**
 * Get all available base stories (templates)
 * @returns {Promise<Array>} List of base stories
 */
export async function getBaseStories() {
  return apiCall('/base-stories');
}

/**
 * Create a new user story based on a template
 * @param {string} userId - User ID
 * @param {string} baseStoryId - Base story template ID
 * @param {string} title - Optional custom title
 * @returns {Promise<Object>} The created story
 */
export async function createStory(userId, baseStoryId, title = null) {
  return apiCall('/stories', 'POST', {
    userId,
    baseStoryId,
    title
  });
}

/**
 * Get a list of stories for a user
 * @param {string} userId - User ID
 * @param {boolean} includeCompleted - Whether to include completed stories
 * @returns {Promise<Array>} List of stories
 */
export async function getUserStories(userId, includeCompleted = false) {
  return apiCall(`/stories?userId=${userId}&includeCompleted=${includeCompleted}`);
}

/**
 * Get detailed information about a specific story
 * @param {string} storyId - Story ID
 * @returns {Promise<Object>} Story details
 */
export async function getStoryDetails(storyId) {
  return apiCall(`/stories/${storyId}`);
}

/**
 * Generate the next segment of a story
 * @param {string} storyId - Story ID
 * @param {string} userId - User ID
 * @param {number} currentTurnNumber - Current turn number
 * @param {object} action - User action (choice or customInput)
 * @param {object} debugConfig - Optional debug configuration
 * @returns {Promise<Object>} Generated story segment
 */
export async function generateStorySegment(storyId, userId, currentTurnNumber, action, debugConfig = null) {
  return apiCall('/generate-segment', 'POST', {
    storyId,
    userId,
    currentTurnNumber,
    action,
    debugConfig
  });
}

/**
 * Mark a story as completed
 * @param {string} storyId - Story ID
 * @returns {Promise<Object>} Result
 */
export async function completeStory(storyId) {
  return apiCall(`/stories/${storyId}/complete`, 'POST');
}

/**
 * Continue a completed story (reset turn counter but keep context)
 * @param {string} storyId - Story ID
 * @returns {Promise<Object>} Result
 */
export async function continueStory(storyId) {
  return apiCall(`/stories/${storyId}/continue`, 'POST');
}

/**
 * Trigger a manual summarization of a story
 * @param {string} storyId - Story ID
 * @returns {Promise<Object>} Result
 */
export async function summarizeStory(storyId) {
  return apiCall('/summarize', 'POST', { storyId });
}

// Admin API functions (requires admin credentials)

/**
 * Create a new base story template (admin only)
 * @param {object} storyData - Base story data
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Created base story
 */
export async function adminCreateBaseStory(storyData, auth) {
  return apiCall('/admin/base-stories', 'POST', {
    ...storyData,
    auth // Pass auth object containing credentials
  });
}

/**
 * Create a new story prompt (admin only)
 * @param {object} promptData - Prompt data
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Created prompt
 */
export async function adminCreateStoryPrompt(promptData, auth) {
  return apiCall('/admin/story-prompts', 'POST', {
    ...promptData,
    auth // Pass auth object containing credentials
  });
}

/**
 * Assign a prompt to a base story (admin only)
 * @param {string} promptId - Prompt ID
 * @param {string} baseStoryId - Base story ID
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Result
 */
export async function adminAssignPrompt(promptId, baseStoryId, auth) {
  return apiCall('/admin/assign-prompt', 'POST', {
    prompt_id: promptId,
    base_story_id: baseStoryId,
    auth // Pass auth object containing credentials
  });
}

/**
 * Get detailed information about a base story (admin only)
 * @param {string} storyId - Base story ID
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Base story details
 */
export async function adminGetBaseStory(storyId) {
   // GET requests typically don't have a body. Auth needs to be passed differently.
   // Option 1: Query parameters (less secure for credentials)
   // return apiCall(`/admin/base-stories/${storyId}?username=${auth.username}&password=${encodeURIComponent(auth.password)}`, 'GET');

   // Option 2: Custom Headers (better) - requires backend support
   // Requires modifying apiCall to support custom headers

   // Option 3: Use POST/PUT even for GET-like actions if backend supports it to send body
   // return apiCall(`/admin/base-stories/${storyId}/details`, 'POST', { auth }); // Example: using a POST endpoint

   // Option 4: Pass auth in the data object and let apiCall handle it IF backend expects GET with body (non-standard)
   // For this example, assuming the backend allows GET with body or apiCall needs adjustment for headers.
   // As a workaround for now, let's pretend GET can send a body via the existing apiCall structure.
   // *** IMPORTANT: This is non-standard for GET requests ***
   // A better long-term solution is custom headers or changing backend endpoints.
   return apiCall(`/admin/base-stories/${storyId}`); // Pass auth in data for GET (non-standard)

}

/**
 * Update a base story (admin only)
 * @param {string} storyId - Base story ID
 * @param {object} storyData - Updated story data
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Result
 */
export async function adminUpdateBaseStory(storyId, storyData, auth) {
  return apiCall(`/admin/base-stories/${storyId}`, 'PUT', {
    ...storyData,
    auth // Pass auth object containing credentials
  });
}

/**
 * Toggle a base story's active status (admin only)
 * @param {string} storyId - Base story ID
 * @param {boolean} active - New active status
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Result
 */
export async function adminToggleBaseStory(storyId, active, auth) {
  // PUT request, can include auth in body
  return apiCall(`/admin/toggle-base-story/${storyId}?active=${active}`, 'PUT', { auth });
}


// --- START OF Authentication Service ---


/**
 * Authentication service for handling user login/logout
 */

// Mock user data for demo purposes
const DEMO_USERS = [
    { id: 'admin-123', username: 'admin', password: 'storyteller123', role: 'admin' },
    { id: 'user-456', username: 'user', password: 'password123', role: 'user' }
  ];

  // Storage key for local storage
  const USER_STORAGE_KEY = 'interactive_story_user';

  /**
   * Attempt to log in a user
   * @param {string} username - Username
   * @param {string} password - Password
   * @returns {object|null} User object if successful, null if failed
   */
  export function login(username, password) {
    // Find matching user
    const user = DEMO_USERS.find(
      u => u.username === username && u.password === password
    );

    if (user) {
      // Create a safe user object (without password)
      const safeUser = {
        id: user.id,
        username: user.username,
        role: user.role
      };

      // Store in local storage
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(safeUser));
      return safeUser;
    }

    return null;
  }

  /**
   * Log out the current user
   */
  export function logout() {
    localStorage.removeItem(USER_STORAGE_KEY);
  }

  /**
   * Get the currently logged in user
   * @returns {object|null} Current user or null if not logged in
   */
  export function getCurrentUser() {
    // Check if we're in a browser environment
    if (typeof window === 'undefined') {
      return null;
    }

    const userJson = localStorage.getItem(USER_STORAGE_KEY);
    if (!userJson) {
      return null;
    }

    try {
      return JSON.parse(userJson);
    } catch (e) {
      console.error('Error parsing user from localStorage:', e);
      return null;
    }
  }

  /**
   * Check if the current user is an admin
   * @returns {boolean} True if user is admin
   */
  export function isAdmin() {
    const user = getCurrentUser();
    return user?.role === 'admin';
  }

  /**
   * Get the admin credentials (username/password) for API calls.
   * WARNING: Retrieving raw passwords like this is insecure.
   * This is suitable ONLY for this mock/demo setup.
   * @returns {object|null} Object with { username, password } or null if not admin/logged in.
   */
  export function getAdminCredentials() {
    const user = getCurrentUser();
    console.log(user)
    if (user && user.role === 'admin') {
      // Find the full user data (including password) from the mock list
      const adminUser = DEMO_USERS.find(u => u.id === user.id);
      console.log(adminUser)
      if (adminUser) {
        // Return the credentials structure expected by the backend API
        return {
          username: adminUser.username,
          password: adminUser.password
        };
      }
    }
    // Not logged in or not an admin
    return null;
  }

  export async function adminDeleteBaseStory(storyId, adminCredentials) {
    if (!adminCredentials) {
      throw new Error("Admin credentials required");
    }
    const response = await fetch(`${API_BASE_URL}/admin/base-stories/${storyId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        // Assuming basic auth or a token is needed based on your adminCredentials structure
        // Example for basic auth:
        'Authorization': 'Basic ' + btoa(`${adminCredentials.username}:${adminCredentials.password}`),
        // Example for token:
        // 'Authorization': `Bearer ${adminCredentials.token}`,
      },
    });
  
    if (response.status === 204) {
      return { success: true }; // Successfully deleted
    } else if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch (e) {
        errorData = { detail: response.statusText };
        console.error(`JSON handling erro: ${e}`);
      }
      throw new Error(errorData.detail || `Failed to delete base story (status ${response.status})`);
    }
    // Should not reach here for 204, but as fallback
    return { success: true };
  }
  
  // --- NEW: Delete Story Prompt Function ---
  export async function adminDeleteStoryPrompt(promptId, adminCredentials) {
    if (!adminCredentials) {
      throw new Error("Admin credentials required");
    }
    const response = await fetch(`${API_BASE_URL}/admin/story-prompts/${promptId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        // Add Authorization header as needed (similar to adminDeleteBaseStory)
         'Authorization': 'Basic ' + btoa(`${adminCredentials.username}:${adminCredentials.password}`),
      },
    });
  
    if (response.status === 204) {
      return { success: true }; // Successfully deleted
    } else if (!response.ok) {
       let errorData;
       try {
         errorData = await response.json();
       } catch (e) {
         errorData = { detail: response.statusText };
         console.error(`JSON handling erro: ${e}`);
       }
       throw new Error(errorData.detail || `Failed to delete story prompt (status ${response.status})`);
     }
     // Should not reach here for 204
     return { success: true };
  }
