import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { ragService, Source } from '../../api/services';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  sources?: Source[];
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  currentStep: string | null;
  activeSources: Source[];
  isDrawerOpen: boolean;
  activeSourceId: string | null;
  error: string | null;
}

const initialState: ChatState = {
  messages: [
    {
      id: '1',
      role: 'ai',
      content: "Hello! I'm your Enterprise RAG assistant. I have access to all your uploaded policy documents. Ask me anything about your organization's policies, procedures, or guidelines.\n\n**Tip:** Upload documents first via the Documents tab, then come back here to query them!"
    }
  ],
  isLoading: false,
  currentStep: null,
  activeSources: [],
  isDrawerOpen: false,
  activeSourceId: null,
  error: null,
};

// THE "DELIVERY GUY" (Async Thunk)
// Handles the dirty work of calling the API and managing the lifecycle
export const askQuestion = createAsyncThunk(
  'chat/askQuestion',
  async (query: string, { dispatch, rejectWithValue }) => {
    try {
      // Show thinking steps (Artificial delays for UX)
      const steps = [
        "Analyzing your question...",
        "Searching knowledge base...",
        "Reranking relevant chunks...",
        "Generating answer..."
      ];

      for (const step of steps) {
        dispatch(setCurrentStep(step));
        await new Promise(r => setTimeout(r, 600));
      }

      const response = await ragService.query(query);
      return response;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to get response. Please try again.";
      return rejectWithValue(message);
    }
  }
);

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addMessage: (state, action: PayloadAction<Message>) => {
      state.messages.push(action.payload);
    },
    setIsLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
    setCurrentStep: (state, action: PayloadAction<string | null>) => {
      state.currentStep = action.payload;
    },
    setActiveSources: (state, action: PayloadAction<Source[]>) => {
      state.activeSources = action.payload;
    },
    setDrawerOpen: (state, action: PayloadAction<boolean>) => {
      state.isDrawerOpen = action.payload;
    },
    setActiveSourceId: (state, action: PayloadAction<string | null>) => {
      state.activeSourceId = action.payload;
    },
    clearChat: (state) => {
      state.messages = initialState.messages;
      state.activeSources = [];
      state.isDrawerOpen = false;
      state.activeSourceId = null;
      state.error = null;
    }
  },
  // THE "RADIO STATION" (Extra Reducers)
  // Listening for the Thunk's lifecycle stages
  extraReducers: (builder) => {
    builder
      .addCase(askQuestion.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(askQuestion.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentStep = null;
        
        // Add the AI response to the history
        state.messages.push({
          id: Date.now().toString(),
          role: 'ai',
          content: action.payload.answer,
          sources: action.payload.sources
        });
      })
      .addCase(askQuestion.rejected, (state, action) => {
        state.isLoading = false;
        state.currentStep = null;
        state.error = action.payload as string;

        // Add an error message to the history
        state.messages.push({
          id: Date.now().toString(),
          role: 'ai',
          content: `⚠️ **Error:** ${action.payload}\n\nPlease make sure you have uploaded documents and try again.`
        });
      });
  }
});

export const { 
  addMessage, 
  setIsLoading, 
  setCurrentStep, 
  setActiveSources, 
  setDrawerOpen, 
  setActiveSourceId,
  clearChat
} = chatSlice.actions;

export default chatSlice.reducer;
