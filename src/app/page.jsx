"use client"

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import styles from '../styles/Home.module.css';
import * as authService from '../services/auth';
import useWindowWidth from '../hooks/useWindowWidth';

// Constants
const MAX_CUSTOM_INPUT_LENGTH = 150;
const DEFAULT_TEMPERATURE = 0.7;

// Default system prompts for debugging purposes
const DEFAULT_SYSTEM_PROMPTS = {
  default: `
  Du bist ein klassischer Erzähler im Stil deutscher Volksmärchen. Deine Sprache ist kindgerecht, bildhaft und leicht verständlich geeignet für Kinder zwischen 6 und 10 Jahren. 
  Du schreibst ausschließlich in: der dritten Person Singular, der Vergangenheitsform (Präteritum), einem märchentypischen Ton: ruhig, geheimnisvoll, poetisch, aber klar. Beispiel: „Der Mond schien silbern auf den moosigen Pfad, als Rotkäppchen ihren ersten Schritt ins Dunkel wagte.
  Vermeide vollständig: moderne Begriffe, Konzepte oder Objekte (z.B. Handy, Firma, Polizei, Auto), Gewalt ohne moralischen Kontext, Ironie, Sarkasmus oder Meta-Kommentare, Fremdwörter, Anglizismen oder komplizierte Satzstrukturen. Negativ-Beispiel: „Plötzlich kam ein Polizeiwagen angerast."
  Stilmittel, die bevorzugt verwendet werden sollen: stimmungsvolle Bilder, sanfte Wiederholungen und rhythmische Satzführung, archetypische Märchenfiguren und -orte
  Aktuelles Märchen: "{request.taleId}"
  Hier ist die bisherige Handlung: {current_summary}
  {original_tale_context} 
  Die Handlung soll sich besonders an den letzten Nutzerentscheidungen und history entries orientieren.
  Verfasse eine neue kurze Szene mit 6 bis 10 Sätzen. Strukturiere jede Szene nach folgendem Muster:
  1. Einstieg in die Situation oder Umgebung  
  2. Ein zentrales Ereignis oder eine neue Wendung  
  3. Abschluss mit offenem Ende, das eine neue Entscheidung oder Entwicklung vorbereitet
  Diese Szene soll: logisch und kohärent auf den bisherigen Verlauf aufbauen, innerhalb des etablierten Märchenrahmens bleiben, eine originelle Wendung darstellen, offen genug enden, um eine weitere Entscheidung zu ermöglichen

  Bevor du antwortest, prüfe: Ist die Szene stilistisch und thematisch einwandfrei im Märchengenre verankert? Ist sie altersgerecht, logisch und frei von modernen oder stilfremden Elementen?
  Priorisiere in deiner Geschichte immer die letzte Auswahl "My Choice:". Falls du bei einer Frage unsicher bist: Überarbeite die Szene vollständig.
  Gib ausschließlich den Märchentext aus. Verzicht auf Einleitungen, Erklärungen oder Meta-Kommentare. Liefere den Text als kohärente Erzählpassage " keine Aufzählung. Beginne direkt mit der ersten Zeile der Geschichte.
  HANDLUNGSOPTIONEN
  Erzeuge die Handlungsoptionen unmittelbar nach der Szene, ohne Zwischenkommentar oder Einleitung, gib drei Entscheidungsoptionen für die Nutzer aus, damit sie die Geschichte aktiv mitgestalten kann:
  1. **Option A – Storynahe Fortsetzung**  
     Eine Handlung, die erwartbar und logisch auf die Szene folgt und den traditionellen Märchenverlauf weiterführt.
  2. **Option B – Alternative Wendung**  
     Eine kreative, aber genre- und stilgerechte Abweichung vom bekannten Verlauf. Diese Option darf überraschend sein, aber muss in der Märchenwelt glaubwürdig bleiben. Stelle sicher, dass sich Option A und B in Handlung, Ton oder Risiko deutlich unterscheiden, um eine echte Wahlmöglichkeit zu bieten.
  Jede Option soll sprachlich einfach, stimmungsvoll und kindgerecht formuliert sein. Die Vorschläge müssen **zur erzählten Szene passen**, dürfen aber **nicht deren Inhalt wiederholen**.
  Format your entire response content ONLY as a valid JSON object string, DONT use markdown and keep the output format cause its very important: {{"storySegment": "...", "choices": ["...", "..."]}}`,
  short: `Erzähle eine kurze kindgerechte Version dieser Geschichte im Märchenstil. Gib genau zwei Optionen zur Auswahl.`,
  experimental: `Sei ein kreativer, moderner Märchenerzähler. Füge unerwartete Wendungen ein, während du einen kindgerechten Ton beibehältst.`
};

// Available models for selection
const AVAILABLE_MODELS = {
  story: [
    { id: "google/gemini-2.0-flash-exp:free", name: "Gemini 2.0 Flash" },
    { id: "google/gemini-2.5-pro-exp-03-25", name: "Gemini 2.5 Pro" },
    { id: "deepseek/deepseek-chat-v3-0324:free", name: "Deepseek V3" },
    { id: "deepseek/deepseek-r1:free", name: "Deepseek R1" },
    { id: "deepseek/deepseek-r1-distill-llama-70b:free", name: "Deepseek R1 Distill Llama70b" },
    { id: "google/gemma-3-27b-it:free", name: "Gemma 3 27b" },
    { id: "meta-llama/llama-4-maverick:free", name: "Llama 4 Maverick" },
    { id: "meta-llama/llama-3.3-70b-instruct:free", name: "Llama 3.3 70b" },
    { id: "thudm/glm-z1-32b:free", name: "GLM Z1 32b" },
    { id: "thudm/glm-4-32b:free", name: "GLM 4 32b" },
    { id: "rekaai/reka-flash-3:free", name: "Reka Flash 3" },
    { id: "mistralai/mistral-small-3.1-24b-instruct:free", name: "Mistral Small 24b" },
    { id: "microsoft/mai-ds-r1:free", name: "Microsoft MAI DS R1" },
    { id: "nvidia/llama-3.1-nemotron-ultra-253b-v1:free", name: "Nvidia Nemotron 253b" },
    { id: "google/gemini-2.5-flash-preview", name: "!!ACHTUNG KOSTET GELD!!! Gemini 2.5 Flash" },
    
    { id: "mistral-small-22b-arliai-rpmax-v1.1", name: "LOKAL Mistral Small 22b RP" },
    { id: "mistral-small-24b-arliai-rpmax-v1.4", name: "LOKAL Mistral Small 24b RP" },
    { id: "golden-curry-12b-i1", name: "LOKAL Golden Curry RP" },
    
  ],
  summary: [
    { id: "mistralai/mistral-small-3.1-24b-instruct:free", name: "Mistral Small 24b" },
    { id: "google/gemini-2.0-flash-exp:free", name: "Gemini 2.0 Flash" },
    { id: "meta-llama/llama-3.2-3b-instruct:free", name: "Llama 3.2 3b" },
    { id: "rekaai/reka-flash-3:free", name: "Reka Flash 3" }
  ]
};

const resetStoryState = () => ({
  storyHistory: [],
  currentChoices: [],
  isLoading: false,
  error: null,
  llmError: null,
  isCustomInputVisible: false,
  customInput: '',
  lastAttemptedAction: null,
  currentStoryId: null,
  currentTurnNumber: 0,
  currentSummary: '',
  storyCompleted: false,
  rawResponse: null,
});

// Animation Variants
const pageVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
  exit: { opacity: 0, y: -20, transition: { duration: 0.3, ease: "easeIn" } }
};

const bookCoverVariants = {
  closed: { scaleX: 1, transformOrigin: "left center" },
  open: { scaleX: 0, transition: { duration: 0.8, ease: [0.6, 0.01, -0.05, 0.9] } } // Custom ease for book feel
};

const textSegmentVariants = { // Keep this parent variant
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      delay: 0.1, // Slightly shorter delay before starting
      staggerChildren: 0.01, // Faster character appearance
      when: "beforeChildren"
    }
  }
};

const characterVariants = {
  // Simplify: Just animate opacity, remove the 'y' transform which might cause subtle jumps
  hidden: { opacity: 0 },
  visible: { opacity: 1 }
};

const interactionAreaVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut", delay: 0.3 } }, // Delay slightly after text
    exit: { opacity: 0, y: -20, transition: { duration: 0.2, ease: "easeIn" } }
};

const debugPanelVariantsDesktop = {
  hidden: { x: "100%", opacity: 0 },
  visible: { x: 0, opacity: 1, transition: { type: "spring", stiffness: 120, damping: 20 } },
  exit: { x: "100%", opacity: 0, transition: { duration: 0.2, ease: "easeIn" } }
};

const debugPanelVariantsMobile = {
  // Mobile: Animates from top. Assumes CSS sets position: relative/static
  hidden: { y: "-100%", opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 18 } }, // Adjust spring if needed
  exit: { y: "-100%", opacity: 0, transition: { duration: 0.2, ease: "easeIn" } }
};

const itemVariants = { // For lists like story selection
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
};

const listVariants = {
    visible: { transition: { staggerChildren: 0.1 } }
};
const sentenceVariants = { // Container for words
  hidden: { opacity: 1 }, // Parent is visible instantly
  visible: {
    opacity: 1,
    transition: {
      delay: 0.1,
      staggerChildren: 0.04, // Stagger time per WORD
    }
  }
};

const wordVariants = {
  hidden: { opacity: 0, y: 5 }, // Animate words fading/sliding in
  visible: { opacity: 1, y: 0 }
};

const AnimatedWords = ({ text }) => {
  const shouldReduceMotion = useReducedMotion();

  // Split into words, preserving spaces between them
  // This regex splits by space but keeps the space attached to the preceding word
  const words = text.match(/(\S+\s*)/g) || []; // Handle potential empty text

  return (
    <motion.span
        variants={shouldReduceMotion ? {} : sentenceVariants}
        initial="hidden"
        animate="visible"
        style={{ display: 'inline' }} // Can likely use inline now
    >
      {words.map((word, index) => (
        <motion.span
          key={`${word}-${index}`}
          variants={shouldReduceMotion ? {} : wordVariants}
          style={{ display: 'inline-block', marginRight: word.endsWith(' ') ? 0 : '0.25em' }} // Keep inline-block for word animation, add space if needed
        >
          {word}
        </motion.span>
      ))}
    </motion.span>
  );
};


export default function HomePage() {
  const router = useRouter();
  const windowWidth = useWindowWidth(); // Use the hook
  const isMobileLayout = windowWidth <= 1200;

  // --- Authentication State ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");

  // --- Story State ---
  // Use the reset function for initial state
  const [storyState, setStoryState] = useState(resetStoryState());
  const {
    storyHistory, currentChoices, isLoading, error, llmError,
    isCustomInputVisible, customInput, lastAttemptedAction,
    currentStoryId, currentTurnNumber, currentSummary, storyCompleted,
    rawResponse
  } = storyState;

  // --- UI State ---
  const [viewState, setViewState] = useState('login'); // login, storySelect, userStories, storyDetail

  // --- Data State ---
  const [availableBaseStories, setAvailableBaseStories] = useState([]);
  const [userStories, setUserStories] = useState([]);
  const [dataLoading, setDataLoading] = useState(false);

  // --- Debug UI State ---
  const [debugPanelVisible, setDebugPanelVisible] = useState(false);
  const [selectedStoryModel, setSelectedStoryModel] = useState(AVAILABLE_MODELS.story[0].id);
  const [selectedSummaryModel, setSelectedSummaryModel] = useState(AVAILABLE_MODELS.summary[0].id);
  const [useCustomPrompt, setUseCustomPrompt] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPTS.default);
  const [useCustomSummaryPrompt, setUseCustomSummaryPrompt] = useState(false);
  const [summarySystemPrompt, setSummarySystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(DEFAULT_TEMPERATURE); // Use constant
  const [isNewStoryOpening, setIsNewStoryOpening] = useState(false); // State for book animation

  // Refs
  const storyEndRef = useRef(null);
  // Removed systemPromptRef as it wasn't used for auto-resize logic

  // --- Authentication Effects ---
  useEffect(() => {
    const user = authService.getCurrentUser();
    if (user) {
      setIsAuthenticated(true);
      setCurrentUser(user);
      setViewState('storySelect'); // Go to story selection after login check
    } else {
      setIsAuthenticated(false);
      setCurrentUser(null);
      setViewState('login'); // Ensure login view if not authenticated
    }
  }, []); // Run only once on mount

  // --- Data Loading Effects ---
  // Use useCallback for loading functions passed to useEffect
  const loadBaseStories = useCallback(async () => {
    setDataLoading(true);
    setStoryState(prev => ({ ...prev, error: null })); // Clear previous errors
    try {
      console.log("Loading base stories...");
      const stories = await authService.getBaseStories();
      setAvailableBaseStories(stories);
       console.log("Base stories loaded:", stories.length);
    } catch (err) {
      console.error("Error loading base stories:", err);
      setStoryState(prev => ({ ...prev, error: `Failed to load story templates: ${err.message}` }));
    } finally {
      setDataLoading(false);
    }
  }, []); // Empty dependency array

  const loadUserStories = useCallback(async () => {
    if (!currentUser) return;
    setDataLoading(true);
    setStoryState(prev => ({ ...prev, error: null })); // Clear previous errors
    try {
      console.log("Loading user stories for:", currentUser.id);
      const stories = await authService.getUserStories(currentUser.id); // Assuming this takes userId
      setUserStories(stories);
      console.log("User stories loaded:", stories.length);
    } catch (err) {
      console.error("Error loading user stories:", err);
       setStoryState(prev => ({ ...prev, error: `Failed to load your stories: ${err.message}` }));
    } finally {
      setDataLoading(false);
    }
  }, [currentUser]); // Depends on currentUser

  useEffect(() => {
    if (isAuthenticated && viewState === 'storySelect') {
      loadBaseStories();
    }
    if (isAuthenticated && viewState === 'userStories') {
      loadUserStories();
    }
  }, [isAuthenticated, viewState, loadBaseStories, loadUserStories]); // Rerun if view changes or auth state changes

  // Auto-scroll effect
  useEffect(() => {
    if (storyHistory.length > 0) { // Only scroll if there's history
        // Use timeout to allow animation to start before scrolling
        const timer = setTimeout(() => {
            storyEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
        }, 100); // Adjust delay as needed
        return () => clearTimeout(timer);
    }
  }, [storyHistory]); // Runs when storyHistory changes

  // Reset default prompt when toggling custom mode
  useEffect(() => {
    if (!useCustomPrompt) {
      setSystemPrompt(DEFAULT_SYSTEM_PROMPTS.default);
    }
  }, [useCustomPrompt]);

  // --- State Update Wrapper ---
  // Helper to simplify updating the combined story state object
  const updateStoryState = (newState) => {
    setStoryState(prev => ({ ...prev, ...newState }));
  };

  // --- Core Story Logic Functions ---

  const generateStorySegment = useCallback(async (action, storyIdToUse, turnNumberToUse) => {
    if (!currentUser || !storyIdToUse || isLoading) {
        console.warn("generateStorySegment called prematurely or while loading", { hasUser: !!currentUser, storyIdToUse, isLoading });
        return; // Exit if conditions not met
    }
    console.log(`Generating segment for story ${storyIdToUse}, turn ${turnNumberToUse}, action:`, action);

    // Store action for retry BEFORE setting loading state
    updateStoryState({ lastAttemptedAction: { action, turnNumber: turnNumberToUse }});

    // Tentative visual update (will be reverted on error)
    let visualUpdate = null;
    if (action.choice) {
      visualUpdate = { type: 'choice', text: `> ${action.choice}` };
    } else if (action.customInput) {
      visualUpdate = { type: 'userInput', text: `> (Custom) ${action.customInput}` };
    }

    // Set loading state and clear choices/inputs
    updateStoryState({
        isLoading: true,
        error: null,
        llmError: null,
        currentChoices: [],
        customInput: '',
        isCustomInputVisible: false,
        // Add tentative update to history ONLY IF visualUpdate exists
        ...(visualUpdate && { storyHistory: [...storyState.storyHistory, visualUpdate] })
    });


    try {
      let debugConfig = { // Always include debug config structure now
          storyModel: selectedStoryModel,
          summaryModel: selectedSummaryModel,
          temperature: temperature,
          includeRawResponse: true // Request raw response for debug panel
      };
      if (useCustomPrompt) debugConfig.systemPrompt = systemPrompt;
      if (useCustomSummaryPrompt) debugConfig.summarySystemPrompt = summarySystemPrompt;

      const response = await authService.generateStorySegment(
        storyIdToUse,
        currentUser.id, // Pass userId if required by backend
        turnNumberToUse, // Use the correct turn number passed to the function
        action,
        debugConfig
      );

      console.log("generateStorySegment API response:", response);

      // SUCCESS: Update state with response data
      updateStoryState({
        currentChoices: response.choices || [], // Ensure choices is an array
        currentTurnNumber: response.nextTurnNumber,
        currentSummary: response.updatedSummary,
        // Replace tentative history update with confirmed story segment
        storyHistory: [
            // Keep history *before* the tentative update
            ...(visualUpdate ? storyState.storyHistory : storyState.storyHistory),
            // Add the user action that *led* to this segment (if not already added)
            ...(visualUpdate && !storyState.storyHistory.includes(visualUpdate) ? [visualUpdate] : []),
             // Add the actual story segment
            { type: 'story', text: response.storySegment }
        ],
        rawResponse: response.rawResponse || null, // Store raw response
        llmError: response.errorMessage || null,
        lastAttemptedAction: null, // Clear attempted action on success
        isLoading: false // Set loading false *last*
      });

    } catch (err) {
      console.error("Error generating story segment:", err);
      // FAILURE: Revert optimistic UI changes and set error
      updateStoryState({
        error: `Failed to generate story: ${err.message || 'Unknown error'}`,
        isLoading: false,
        // Remove the tentatively added user action from history
        storyHistory: visualUpdate
           ? storyState.storyHistory.filter(item => item !== visualUpdate)
           : storyState.storyHistory,
         // Keep lastAttemptedAction for retry button
      });
    }
  }, [currentUser, isLoading, storyState.storyHistory, selectedStoryModel, selectedSummaryModel, temperature, useCustomPrompt, systemPrompt, useCustomSummaryPrompt, summarySystemPrompt]); // Include all dependencies


  const loadStoryDetails = useCallback(async (storyId) => {
    if (!storyId) return;
    setDataLoading(true);
    updateStoryState(resetStoryState()); // Reset story state
    try {
      console.log(`Loading details for story ${storyId}...`);
      // Assuming admin credentials are not needed for regular users to get their own story
      const storyDetails = await authService.getStoryDetails(storyId);
      console.log(`Details received for story ${storyId}:`, storyDetails);

      const formattedHistory = (storyDetails.storyMessages || []).map(msg => ({ // Add default empty array
        type: msg.type,
        text: msg.content
      }));

      // *** USE THE FETCHED last_choices ***
      const initialChoices = storyDetails.last_choices || []; // Get choices from response

      updateStoryState({
        currentStoryId: storyId,
        currentTurnNumber: storyDetails.currentTurnNumber,
        currentSummary: storyDetails.currentSummary || '',
        storyCompleted: storyDetails.isCompleted,
        storyHistory: formattedHistory,
        currentChoices: initialChoices, // <-- Set the choices here
      });

      setViewState('storyDetail');

      // Logic for what to do after loading (removed auto-generate)
      if (storyDetails.currentTurnNumber > 0 && !storyDetails.isCompleted && initialChoices.length === 0) {
          console.warn("Loaded existing story, but no choices were available for the current turn.");
          // Maybe show a specific message or a default "continue" action?
          // updateStoryState({ currentChoices: ["Continue the story"] }); // Example fallback
      }

    } catch (err) {
      console.error("Error loading story details:", err);
      updateStoryState({ error: `Failed to load story: ${err.message}` });
      setViewState('userStories');
    } finally {
      setDataLoading(false);
    }
  }, []); // Dependenci


  const createNewStory = useCallback(async (baseStoryId) => {
    if (!currentUser || isLoading) return;
    console.log(`Creating new story from base ${baseStoryId}`);

    updateStoryState({ ...resetStoryState(), isLoading: true }); // Reset and set loading

    try {
      const newStory = await authService.createStory(
        currentUser.id, // Assuming API needs userId
        baseStoryId
      );
      console.log("New story created:", newStory);

      // Set minimal state needed for the first generation call
      const storyId = newStory.id;
      const turnNumber = newStory.currentTurnNumber; // Should be 0

      // Update state *before* generating segment
       updateStoryState({
           currentStoryId: storyId,
           currentTurnNumber: turnNumber,
           currentSummary: newStory.currentSummary || '',
           storyCompleted: false,
           isLoading: true // Keep loading true for generate call
       });

       // Trigger book opening animation *before* generating segment
      setIsNewStoryOpening(true);
      setViewState('storyDetail');

      // Wait briefly for animation to start, then generate first segment
      // Using await here ensures the story segment generation completes
      // before potentially changing state again (like setting isLoading to false)
      await new Promise(resolve => setTimeout(resolve, 100)); // Small delay
      await generateStorySegment({ choice: "Beginne die Geschichte" }, storyId, turnNumber);

    } catch (err) {
      console.error("Error creating story:", err);
      updateStoryState({
          error: `Failed to create story: ${err.message}`,
          isLoading: false // Ensure loading is off on error
      });
      setIsNewStoryOpening(false);
      setViewState('storySelect'); // Go back to selection on failure
    }
    // isLoading state is handled within generateStorySegment or the catch block
  }, [currentUser, isLoading, generateStorySegment]); // Depends on these


  // --- Authentication Handlers ---
  const handleLogin = async (e) => { // Make async if auth involves API calls
    e.preventDefault();
    setAuthError(""); // Clear previous errors
    try {
      // Replace with actual async API call if needed
      // const user = await authService.loginAsync(username, password);
      const user = authService.login(username, password); // Using synchronous for now

      if (user) {
        setIsAuthenticated(true);
        setCurrentUser(user);
        setViewState('storySelect'); // Navigate after successful login
      } else {
        setAuthError("Invalid username or password");
        setIsAuthenticated(false);
        setCurrentUser(null);
      }
    } catch (err) {
        console.error("Login error:", err);
        setAuthError(`Login failed: ${err.message}`);
        setIsAuthenticated(false);
        setCurrentUser(null);
    }
  };

  const handleLogout = () => {
    authService.logout();
    setIsAuthenticated(false);
    setCurrentUser(null);
    setStoryState(resetStoryState()); // Reset story state on logout
    setViewState('login');
  };

  // --- Story Navigation Handlers ---
  const handleGoToStorySelect = () => {
    setStoryState(resetStoryState()); // Reset story state when navigating away
    setViewState('storySelect');
    // Data loading triggered by useEffect based on viewState
  };

  const handleGoToUserStories = () => {
    setStoryState(resetStoryState()); // Reset story state when navigating away
    setViewState('userStories');
    // Data loading triggered by useEffect based on viewState
  };

  const handleSelectBaseStory = (baseStoryId) => {
    if (isLoading || dataLoading) return; // Prevent action while loading
    // Reset any specific selection state if needed
    createNewStory(baseStoryId); // Let createNewStory handle state and navigation
  };

  const handleSelectUserStory = (storyId) => {
     if (isLoading || dataLoading) return; // Prevent action while loading
    loadStoryDetails(storyId); // Let loadStoryDetails handle state and navigation
  };


  // --- Story Completion/Continuation ---
  const handleStoryCompletion = useCallback(async () => {
    if (!currentStoryId || isLoading) return;
    updateStoryState({ isLoading: true });
    try {
      await authService.completeStory(currentStoryId);
      updateStoryState({
          storyCompleted: true,
          // Provide clear choices for completed state
          currentChoices: ["Return to Story Selection", "Start a New Story"],
          isLoading: false
       });
    } catch (err) {
      console.error("Error completing story:", err);
      updateStoryState({ error: `Failed to complete story: ${err.message}`, isLoading: false });
    }
  }, [currentStoryId, isLoading]);

  // Continue story logic might need adjustment depending on backend implementation
  // For now, let's assume it resets the completed flag and maybe adds a note.
  const handleStoryContinuation = useCallback(async () => {
     if (!currentStoryId || isLoading) return;
     updateStoryState({ isLoading: true });
     try {
       // Assuming backend just resets the flag and returns updated turn (if needed)
       const result = await authService.continueStory(currentStoryId);
       updateStoryState({
           storyCompleted: false,
           currentTurnNumber: result.currentTurnNumber, // Update turn if backend provides it
           currentChoices: [], // Clear choices, user needs to act or we generate
           isLoading: false
       });
       // Optionally, generate a continuation segment immediately
       // await generateStorySegment({ choice: "Continue the adventure" }, currentStoryId, result.currentTurnNumber);
       // Or just let the user choose an action now the story is not 'completed'
     } catch (err) {
       console.error("Error continuing story:", err);
       updateStoryState({ error: `Failed to continue story: ${err.message}`, isLoading: false });
     }
  }, [currentStoryId, isLoading, generateStorySegment]);


  // --- Interaction Handlers ---
  const handleChoiceClick = (choice) => {
    if (isLoading) return;

    if (storyCompleted) {
      // Handle choices presented *after* completion
      if (choice === "Return to Story Selection" || choice === "Start a New Story") {
        handleGoToStorySelect();
      }
      // Add other post-completion actions if needed
    } else {
      // Regular story choice: pass current state to generator
      generateStorySegment({ choice }, currentStoryId, currentTurnNumber);
    }
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (!customInput.trim() || isLoading) return;
    generateStorySegment({ customInput: customInput.trim() }, currentStoryId, currentTurnNumber);
  };

  const handleRetry = () => {
    if (!lastAttemptedAction || isLoading) return;
    console.log("Retrying action:", lastAttemptedAction);
    updateStoryState({ error: null, llmError: null }); // Clear errors before retry
    // Pass the stored action and turn number for the retry attempt
    generateStorySegment(lastAttemptedAction.action, currentStoryId, lastAttemptedAction.turnNumber);
  };

  const handleInputChange = (e) => {
    if (e.target.value.length <= MAX_CUSTOM_INPUT_LENGTH) {
      updateStoryState({ customInput: e.target.value });
    }
  };


  // --- UI Toggle Handlers ---
  const toggleCustomInput = () => updateStoryState({ isCustomInputVisible: !isCustomInputVisible });
  const toggleDebugPanel = () => setDebugPanelVisible(prev => !prev);
  const toggleCustomPrompt = () => setUseCustomPrompt(prev => !prev);
  const toggleCustomSummaryPrompt = () => setUseCustomSummaryPrompt(prev => !prev);

  // --- Form Handlers ---
  const handleSystemPromptChange = (e) => setSystemPrompt(e.target.value);
  const handleSummarySystemPromptChange = (e) => setSummarySystemPrompt(e.target.value);
  const handleTemperatureChange = (e) => setTemperature(parseFloat(e.target.value));

  // Auto-resize textarea (can be simplified if not needed)
  const autoResizeTextarea = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
  };


  // --- Render Login Page ---
  if (viewState === 'login') {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.authContainer}>
          <h1 className={styles.authTitle}>Taleon</h1>
          
          <form onSubmit={handleLogin} className={styles.authForm}>
            {authError && <p className={styles.authError}>{authError}</p>}
            
            <div className={styles.formGroup}>
              <label htmlFor="username">Username</label>
              <input 
                type="text" 
                id="username" 
                value={username} 
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            
            <div className={styles.formGroup}>
              <label htmlFor="password">Password</label>
              <input 
                type="password" 
                id="password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            
            <button type="submit" className={styles.authButton}>Login</button>
          </form>
          
          <div className={styles.loginInfo}>
            <p><strong>Demo Users:</strong></p>
            <p>Admin - username: admin, password: storyteller123</p>
            <p>User - username: user, password: password123</p>
          </div>
        </div>
      </div>
    );
  }

  // --- Page Container for Authenticated Users ---
  // Authenticated Views
  return (
    <div className={`${styles.pageContainer} ${debugPanelVisible && isMobileLayout  ? styles.pageContainerMobileDebug : ''}` }>
      {/* Debug Panel (Animated) */}
      <AnimatePresence>
        {debugPanelVisible && (
          <motion.div
            key="debugPanel"
            className={styles.debugPanel}
            variants={isMobileLayout ? debugPanelVariantsMobile : debugPanelVariantsDesktop}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {/* LLM Error Display */}
            {llmError && (
              <div className={styles.debugSection}>
                <h4>LLM Error</h4>
                <div className={styles.errorContainer} style={{backgroundColor: '#fff0f1', border: '1px solid #ffccd0'}}> {/* Inline style for debug-specific error */}
                  <p className={styles.llmErrorText}>{llmError}</p>
                </div>
              </div>
            )}

             {/* Model Selectors */}
            <div className={styles.debugSection}>
                 <h4>Models & Temperature</h4>
                <div className={styles.modelSelectors}>
                    <div className={styles.modelSelector}>
                        <label>Story Generation Model:</label>
                        <select value={selectedStoryModel} onChange={(e) => setSelectedStoryModel(e.target.value)}>
                            {AVAILABLE_MODELS.story.map(model => (<option key={model.id} value={model.id}>{model.name}</option>))}
                        </select>
                    </div>
                    <div className={styles.modelSelector}>
                        <label>Summary Generation Model:</label>
                        <select value={selectedSummaryModel} onChange={(e) => setSelectedSummaryModel(e.target.value)}>
                             {AVAILABLE_MODELS.summary.map(model => (<option key={model.id} value={model.id}>{model.name}</option>))}
                        </select>
                    </div>
                </div>
                 {/* Temperature Slider */}
                 <div className={styles.temperatureControl}>
                    <div className={styles.sliderContainer}>
                        <input type="range" min="0" max="1" step="0.01" value={temperature} onChange={handleTemperatureChange} className={styles.slider} />
                        <div className={styles.sliderLabels}><span>Predictable</span><span>{temperature.toFixed(2)}</span><span>Creative</span></div>
                    </div>
                </div>
            </div>

            {/* System Prompts (Optional - Uncomment if needed) */}
            {/* <div className={styles.debugSection}> ... </div> */}

            {/* Raw Response */}
            {rawResponse && (
              <div className={styles.debugSection}>
                <h4>Raw LLM Response</h4>
                <pre className={styles.rawResponseDisplay}>
                  {typeof rawResponse === 'object' ? JSON.stringify(rawResponse, null, 2) : rawResponse}
                </pre>
              </div>
            )}

            {/* Current State */}
            <div className={styles.debugSection}>
              <h4>Current State</h4>
              <div className={styles.stateDisplay}>
                <div><strong>Story ID:</strong> {currentStoryId || 'None'}</div>
                <div><strong>Turn:</strong> {currentTurnNumber}</div>
                <div className={styles.summaryDisplay}>
                  <strong>Current Summary:</strong>
                  <div className={styles.summaryText}>{currentSummary || 'Not generated yet.'}</div>
                </div>
                 <div><strong>Is Completed:</strong> {storyCompleted ? 'Yes' : 'No'}</div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* Main Book Structure */}
      <motion.div
        className={`${styles.bookContainer} ${debugPanelVisible ? styles.withDebugPanel : ''}`}
        initial={false} // No initial animation for the container itself unless needed
        animate={{ marginRight: debugPanelVisible && !isMobileLayout ? 320 : 0 }} // Animate margin change
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        {/* Header */}
        <div className={styles.headerArea}>
          <h1 className={styles.title}>Taleon</h1>
          <div className={styles.navButtons}>
            {/* Navigation Buttons */}
            {viewState !== 'storySelect' && ( <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={styles.navButton} onClick={handleGoToStorySelect}>New Story</motion.button> )}
            {viewState !== 'userStories' && ( <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={styles.navButton} onClick={handleGoToUserStories}>My Stories</motion.button> )}
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`${styles.navButton} ${styles.navButtonDebug}`} onClick={toggleDebugPanel}>{debugPanelVisible ? "Hide Debug" : "Show Debug"}</motion.button>
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={styles.logoutButton} onClick={handleLogout}>Logout</motion.button>
          </div>
        </div>

        {/* Animated View Content */}
        <AnimatePresence mode="wait"> {/* mode="wait" ensures exit animation completes first */}
          {viewState === 'storySelect' && (
            <motion.div key="storySelect" variants={pageVariants} initial="hidden" animate="visible" exit="exit" className={styles.startContainer}>
              <h2 className={styles.startTitle}>Choose a Tale to Begin</h2>
              {/* Loading/Error States */}
              {dataLoading && <div className={styles.loadingContainer}><div className={styles.loadingSpinner}></div><p className={styles.loadingText}>Loading available tales...</p></div>}
               <AnimatePresence>
                {error && <motion.p initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} className={styles.errorText}>{error}</motion.p>}
               </AnimatePresence>

              {!dataLoading && !error && availableBaseStories.length === 0 && (<p>No tales found.</p>)}
              {!dataLoading && !error && availableBaseStories.length > 0 && (
                <motion.div className={styles.taleListContainer} variants={listVariants} initial="hidden" animate="visible">
                  {availableBaseStories.map((baseStory) => (
                    <motion.button
                      key={baseStory.id}
                      variants={itemVariants}
                      whileHover={{ scale: 1.03, transition: { duration: 0.15 } }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => handleSelectBaseStory(baseStory.id)}
                      className={styles.startButton}
                      disabled={isLoading}
                    >
                      <h3>{baseStory.title}</h3>
                      <span className={styles.storyDescription}>{baseStory.description}</span>
                    </motion.button>
                  ))}
                </motion.div>
              )}
            </motion.div>
          )}

          {viewState === 'userStories' && (
             <motion.div key="userStories" variants={pageVariants} initial="hidden" animate="visible" exit="exit" className={styles.startContainer}>
               <h2 className={styles.startTitle}>Your Stories</h2>
               {/* Loading/Error States */}
                {dataLoading && <div className={styles.loadingContainer}><div className={styles.loadingSpinner}></div><p className={styles.loadingText}>Loading your stories...</p></div>}
                 <AnimatePresence>
                    {error && <motion.p initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} className={styles.errorText}>{error}</motion.p>}
                 </AnimatePresence>

                {!dataLoading && !error && userStories.length === 0 && (
                    <motion.div variants={itemVariants} className={styles.noStoriesContainer}>
                        <p>You haven't created any stories yet.</p>
                        <motion.button
                          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }}
                          onClick={handleGoToStorySelect}
                          className={`${styles.startButton} ${styles.newStoryButton}`} // Reuse styles
                        > Start a New Story </motion.button>
                    </motion.div>
                )}
                {!dataLoading && !error && userStories.length > 0 && (
                    <motion.div className={styles.userStoriesContainer} variants={listVariants} initial="hidden" animate="visible">
                        {userStories.map((story) => (
                            <motion.div key={story.id} variants={itemVariants} whileHover={{ y: -5 }} className={styles.userStoryCard}>
                                <h3>{story.title}</h3>
                                <p>Based on: {story.baseStoryTitle}</p>
                                <p>Turn: {story.currentTurnNumber}</p>
                                <p>Last updated: {new Date(story.updatedAt).toLocaleDateString()}</p>
                                <motion.button
                                    whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                                    onClick={() => handleSelectUserStory(story.id)}
                                    className={styles.continueButton}
                                    disabled={isLoading}
                                > {story.isCompleted ? 'View Completed Story' : 'Continue Story'} </motion.button>
                            </motion.div>
                        ))}
                        <motion.button
                            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                            onClick={handleGoToStorySelect}
                            className={styles.newStoryButton}
                        > Start a New Story </motion.button>
                    </motion.div>
                )}
             </motion.div>
          )}

          {viewState === 'storyDetail' && (
            <motion.div key="storyDetail" variants={pageVariants} initial="hidden" animate="visible" exit="exit" className={styles.contentContainer}>
               {/* Book Opening Animation Overlay */}
               <AnimatePresence>
                 {isNewStoryOpening && !isLoading && ( // Show only when new story starts and not already loading next segment
                   <motion.div
                     key="bookCover"
                     className={styles.bookCover}
                     variants={bookCoverVariants}
                     initial="closed"
                     animate="open"
                     exit="open" // Ensure it animates out if needed
                     onAnimationComplete={() => setIsNewStoryOpening(false)} // Hide after animation
                   >
                     Opening Tale...
                   </motion.div>
                 )}
               </AnimatePresence>

              {/* Story Text Area */}
              <div className={styles.storyArea}>
                 <AnimatePresence initial={false}> {/* Don't animate initial load of history */}
                    {storyHistory.map((item, index) => {const itemClasses = `${styles.storyText} ${styles[item.type] || styles.story}`; // Default to .story if type is missing

                return (
                  <motion.p
                  key={`${currentStoryId}-${item.id || index}`}
                  className={itemClasses}
                  // No initial animation needed on the <p> itself if words animate
                  initial={false} // Or maybe a slight initial fade: initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  animate={false}
                  transition={{ duration: 0 }} // No transition on the <p>
              >
                  {/* Apply AnimatedWords ONLY to the latest 'story' type */}
                  {item.type === 'story' && index === storyHistory.length - 1
                      ? <AnimatedWords text={item.text} />
                      : item.text}
              </motion.p>
                );})}
                 </AnimatePresence>
                 <div ref={storyEndRef} /> {/* Scroll target */}
              </div>

              {/* Interaction Area */}
              <AnimatePresence mode="wait">
                {isLoading && (
                    <motion.div
                        key="loading"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className={styles.loadingContainer}
                    >
                        <div className={styles.loadingSpinner}></div>
                        <p className={styles.loadingText}>The quill scribbles furiously...</p>
                    </motion.div>
                )}

                {(error || llmError) && !isLoading && (
                     <motion.div
                        key="error"
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className={styles.errorContainer}
                    >
                        {error && <p className={styles.errorText}>A smudge on the page: {error}</p>}
                        {llmError && <p className={styles.llmErrorText}>The ink whispers an error: {llmError}</p>}
                        {lastAttemptedAction && (
                            <motion.button
                                whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                                onClick={handleRetry}
                                className={styles.retryButton}
                                disabled={isLoading}
                            > Retry Last Action </motion.button>
                        )}
                    </motion.div>
                )}

                {!isLoading && !error && currentChoices.length > 0 && (
                   <motion.div
                        key={`choices-${currentTurnNumber}`} // Key change triggers animation
                        variants={interactionAreaVariants}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                        className={styles.interactionArea}
                    >
                     <h3 className={styles.interactionPrompt}>What happens next?</h3>
                     <div className={styles.choicesArea}>
                        <motion.div className={styles.choiceButtonsContainer} variants={listVariants}>
                            {currentChoices.map((choice, index) => (
                                <motion.button
                                    key={index}
                                    variants={itemVariants}
                                    whileHover={{ scale: 1.03, y: -2, transition: { duration: 0.1 } }}
                                    whileTap={{ scale: 0.98 }}
                                    onClick={() => handleChoiceClick(choice)}
                                    className={styles.choiceButton}
                                    disabled={isLoading}
                                > {choice} </motion.button>
                            ))}
                        </motion.div>

                        {!storyCompleted && (
                        <>
                           <AnimatePresence>
                            {isCustomInputVisible && (
                                <motion.div
                                    key="customInput"
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: 0.3 }}
                                    className={styles.customInputContainer}
                                >
                                    <label htmlFor="customAction" className={styles.customInputLabel}>Or, dictate your own fate:</label>
                                    <textarea id="customAction" value={customInput} onChange={handleInputChange} placeholder={`Max ${MAX_CUSTOM_INPUT_LENGTH} characters...`} rows="3" className={styles.customInputTextarea} maxLength={MAX_CUSTOM_INPUT_LENGTH} disabled={isLoading} autoFocus />
                                    <div className={styles.customInputFooter}>
                                        <span className={styles.customInputCounter}>{customInput.length}/{MAX_CUSTOM_INPUT_LENGTH}</span>
                                        <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleCustomSubmit} className={styles.customInputButton} disabled={isLoading || !customInput.trim()}>Declare Action</motion.button>
                                    </div>
                                </motion.div>
                            )}
                           </AnimatePresence>

                            <div className={styles.toggleCustomContainer}>
                                <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={toggleCustomInput} className={styles.toggleCustomInputButton} disabled={isLoading}>{isCustomInputVisible ? 'Cancel Custom Action' : 'Write Custom Action'}</motion.button>
                                {!storyCompleted && currentTurnNumber > 5 && ( // Show complete button logic
                                    <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleStoryCompletion} className={styles.completeStoryButton} disabled={isLoading}>Complete Story</motion.button>
                                )}
                                {storyCompleted && ( // Show continue button if completed
                                    <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleStoryContinuation} className={styles.continueButton} disabled={isLoading}>Continue This Tale?</motion.button>
                                )}
                            </div>
                        </>
                        )}
                     </div>
                   </motion.div>
                )}

                {/* End Message */}
                {!isLoading && !error && currentChoices.length === 0 && storyHistory.length > 0 && !storyCompleted && (
                     <motion.p key="end" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} className={styles.endMessage}>The ink dries... for now.</motion.p>
                )}
                {!isLoading && !error && storyCompleted && currentChoices.length === 0 && ( // Message specific to completed stories with no action choices
                     <motion.p key="completed-end" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} className={styles.endMessage}>The tale is told. Return to your library or start anew?</motion.p>
                     // Add buttons here to navigate if needed, or rely on header nav
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>

      </motion.div> {/* End Book Container */}

      

    </div> // End Page Container
  );
}