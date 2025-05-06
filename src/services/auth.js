// --- START OF COMPLETE services/auth.js ---

// Define backend URL (use environment variable in real app)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'; // Use NEXT_PUBLIC_ for client-side env vars

/**
 * Helper function to make API calls
 * @param {string} endpoint - API endpoint (e.g., /base-stories)
 * @param {string} method - HTTP method (GET, POST, etc)
 * @param {object | null} data - Data to send in the request body
 * @param {object | null} auth - Optional auth credentials { username, password } for header/body injection
 * @returns {Promise} Promise that resolves to the API response
 */
async function apiCall(endpoint, method = 'GET', data = null, auth = null) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
  };

  // Add Authorization header if auth credentials are provided
  if (auth && auth.username && auth.password) {
      headers['Authorization'] = 'Basic ' + btoa(`${auth.username}:${auth.password}`);
  }

  const options = {
    method,
    headers,
    // credentials: 'include', // Include if using session cookies
  };

  // Only add body for relevant methods and if data exists
  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(url, options);

    // Handle empty response body (e.g., 204 No Content for DELETE)
    if (response.status === 204) {
        return { success: true }; // Indicate success for 204
    }

    // Try to parse JSON, handle potential errors
    let responseData;
    try {
        responseData = await response.json();
    } catch (e) {
        // If JSON parsing fails but status is OK (e.g., 200 with empty body), treat as success? Or specific error?
        if (response.ok) {
             console.warn(`API call to ${method} ${endpoint} returned OK status (${response.status}) but failed JSON parsing. Assuming success with no data. error ${e}`);
             return { success: true, data: null }; // Or handle as needed
        }
        // If not OK and JSON fails, throw based on status text
        throw new Error(`API Error: ${response.status} ${response.statusText} (JSON parsing failed)`);
    }

    // Check if response status indicates an error
    if (!response.ok) {
      const errorMessage = responseData.detail || `API Error: ${response.status} ${response.statusText}`;
      throw new Error(errorMessage);
    }

    // Return the parsed JSON data
    return responseData;

  } catch (error) {
    console.error(`API call failed: ${method} ${endpoint} - ${error.message}`);
    // Re-throw the error so calling functions can handle it
    throw error;
  }
}

// --- Base Story & User Story Functions ---

export async function getBaseStories() {
  return apiCall('/base-stories');
}

export async function createStory(userId, baseStoryId, title = null) {
  return apiCall('/stories', 'POST', { userId, baseStoryId, title });
}

export async function getUserStories(userId, includeCompleted = false) {
  // Pass query params correctly
  const endpoint = `/stories?userId=${encodeURIComponent(userId)}&includeCompleted=${includeCompleted}`;
  return apiCall(endpoint);
}

export async function getStoryDetails(storyId) {
  return apiCall(`/stories/${storyId}`);
}

export async function generateStorySegment(storyId, userId, currentTurnNumber, action, debugConfig = null) {
  return apiCall('/generate-segment', 'POST', { storyId, userId, currentTurnNumber, action, debugConfig });
}

export async function completeStory(storyId) {
  return apiCall(`/stories/${storyId}/complete`, 'POST');
}

export async function continueStory(storyId) {
  return apiCall(`/stories/${storyId}/continue`, 'POST');
}

export async function summarizeStory(storyId) {
  return apiCall('/summarize', 'POST', { storyId });
}

// --- Admin API functions (require admin credentials) ---

// --- Base Story Admin ---

export async function adminCreateBaseStory(storyData, auth) {
  // storyData MUST include story_type_id
  if (!storyData.story_type_id) {
      throw new Error("Story Type ID is required to create a base story.");
  }
  return apiCall('/admin/base-stories', 'POST', storyData, auth);
}

export async function adminGetBaseStory(storyId, auth) {
   // GET request, auth handled by header in apiCall helper
   return apiCall(`/admin/base-stories/${storyId}`, 'GET', null, auth);
}

export async function adminUpdateBaseStory(storyId, storyData, auth) {
   // storyData MUST include story_type_id
   if (!storyData.story_type_id) {
       throw new Error("Story Type ID is required to update a base story.");
   }
  return apiCall(`/admin/base-stories/${storyId}`, 'PUT', storyData, auth);
}

export async function adminToggleBaseStory(storyId, active, auth) {
  // Use PUT, pass data (if any needed beyond query param) and auth
  return apiCall(`/admin/toggle-base-story/${storyId}?active=${active}`, 'PUT', {}, auth);
}

export async function adminDeleteBaseStory(storyId, auth) {
  // DELETE request, auth handled by header
  return apiCall(`/admin/base-stories/${storyId}`, 'DELETE', null, auth);
}

// --- Story Prompt Admin ---

export async function adminCreateStoryPrompt(promptData, auth) {
  return apiCall('/admin/story-prompts', 'POST', promptData, auth);
}

// NEW: Get all prompts (needs backend endpoint)
export async function adminGetAllStoryPrompts(auth) {
    // Assumes backend endpoint GET /admin/story-prompts/all exists
    return apiCall('/admin/story-prompts/all', 'GET', null, auth);
}

export async function adminDeleteStoryPrompt(promptId, auth) {
  return apiCall(`/admin/story-prompts/${promptId}`, 'DELETE', null, auth);
}

// --- Story Type Admin (NEW FUNCTIONS) ---

export async function adminGetStoryTypes(auth) {
  // GET request, auth handled by header
  return apiCall('/admin/story-types', 'GET', null, auth);
}

export async function adminGetStoryTypeDetails(storyTypeId, auth) {
  // GET request, auth handled by header
  return apiCall(`/admin/story-types/${storyTypeId}`, 'GET', null, auth);
}

export async function adminCreateStoryType(storyTypeData, auth) {
  return apiCall('/admin/story-types', 'POST', storyTypeData, auth);
}

export async function adminUpdateStoryType(storyTypeId, storyTypeData, auth) {
  return apiCall(`/admin/story-types/${storyTypeId}`, 'PUT', storyTypeData, auth);
}

export async function adminDeleteStoryType(storyTypeId, auth) {
  return apiCall(`/admin/story-types/${storyTypeId}`, 'DELETE', null, auth);
}

// --- Prompt Assignment Admin (NEW FUNCTIONS) ---

export async function adminAssignPromptToStoryType(promptId, storyTypeId, auth) {
  // Needs backend endpoint POST /admin/story-types/assign-prompt
  return apiCall('/admin/story-types/assign-prompt', 'POST', {
    prompt_id: promptId,
    story_type_id: storyTypeId,
  }, auth);
}

export async function adminRemovePromptFromStoryType(promptId, storyTypeId, auth) {
   // Needs backend endpoint DELETE /admin/story-types/{storyTypeId}/prompts/{promptId}
   return apiCall(`/admin/story-types/${storyTypeId}/prompts/${promptId}`, 'DELETE', null, auth);
}


// --- Authentication Service ---

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
  const user = DEMO_USERS.find(u => u.username === username && u.password === password);
  if (user) {
    const safeUser = { id: user.id, username: user.username, role: user.role };
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(safeUser));
    return safeUser;
  }
  return null;
}

/** Log out the current user */
export function logout() {
  localStorage.removeItem(USER_STORAGE_KEY);
}

/** Get the currently logged in user */
export function getCurrentUser() {
  if (typeof window === 'undefined') return null; // Guard for server-side rendering
  const userJson = localStorage.getItem(USER_STORAGE_KEY);
  if (!userJson) return null;
  try { return JSON.parse(userJson); }
  catch (e) { console.error('Error parsing user from localStorage:', e); return null; }
}

/** Check if the current user is an admin */
export function isAdmin() {
  const user = getCurrentUser();
  return user?.role === 'admin';
}

/**
 * Get admin credentials (username/password) for API calls.
 * WARNING: Insecure for production. Demo only.
 */
export function getAdminCredentials() {
  const user = getCurrentUser();
  if (user && user.role === 'admin') {
    const adminUser = DEMO_USERS.find(u => u.id === user.id);
    if (adminUser) { return { username: adminUser.username, password: adminUser.password }; }
  }
  return null; // Not logged in or not an admin
}

/**
 * Get details of a specific story prompt (admin only)
 * @param {string} promptId - Prompt ID
 * @param {object} auth - Authentication credentials { username, password }
 * @returns {Promise<Object>} Prompt details
 */
export async function adminGetStoryPromptDetails(promptId, auth) {
    return apiCall(`/admin/story-prompts/${promptId}`, 'GET', null, auth);
 }
 
 /**
  * Update an existing story prompt (admin only)
  * @param {string} promptId - Prompt ID
  * @param {object} promptData - Updated prompt data (name, system_prompt, etc.)
  * @param {object} auth - Authentication credentials { username, password }
  * @returns {Promise<Object>} Updated prompt details
  */
 export async function adminUpdateStoryPrompt(promptId, promptData, auth) {
   return apiCall(`/admin/story-prompts/${promptId}`, 'PUT', promptData, auth);
 }