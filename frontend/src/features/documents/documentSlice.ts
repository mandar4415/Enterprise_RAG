import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { ragService } from '../../api/services';

export interface Document {
  id: number;
  filename: string;
  title: string;
  file_size: number;
  created_at: string;
  num_chunks: number;
}

interface DocumentState {
  items: Document[];
  isLoading: boolean;
  isUploading: boolean;
  uploadProgress: string;
  error: string | null;
}

const initialState: DocumentState = {
  items: [],
  isLoading: false,
  isUploading: false,
  uploadProgress: '',
  error: null,
};

// THE "ARCHIVIST" THUNKS
export const fetchDocuments = createAsyncThunk(
  'documents/fetchAll',
  async (_, { rejectWithValue }) => {
    try {
      const response = await ragService.listDocuments();
      return response.documents || [];
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || "Failed to load documents");
    }
  }
);

export const uploadDocument = createAsyncThunk(
  'documents/upload',
  async (file: File, { dispatch, rejectWithValue }) => {
    try {
      dispatch(setUploadProgress('Uploading and processing...'));
      const response = await ragService.uploadDocument(file);
      // After upload, refresh the list
      dispatch(fetchDocuments());
      return response;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || "Upload failed. Please try again.");
    }
  }
);

export const deleteDocument = createAsyncThunk(
  'documents/delete',
  async (id: number, { rejectWithValue }) => {
    try {
      await ragService.deleteDocument(id);
      return id;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || "Failed to delete document");
    }
  }
);

const documentSlice = createSlice({
  name: 'documents',
  initialState,
  reducers: {
    setUploadProgress: (state, action: PayloadAction<string>) => {
      state.uploadProgress = action.payload;
    },
    clearDocError: (state) => {
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    builder
      // Fetch
      .addCase(fetchDocuments.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchDocuments.fulfilled, (state, action: PayloadAction<Document[]>) => {
        state.isLoading = false;
        state.items = action.payload;
      })
      .addCase(fetchDocuments.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Upload
      .addCase(uploadDocument.pending, (state) => {
        state.isUploading = true;
        state.error = null;
      })
      .addCase(uploadDocument.fulfilled, (state) => {
        state.isUploading = false;
        state.uploadProgress = '';
      })
      .addCase(uploadDocument.rejected, (state, action) => {
        state.isUploading = false;
        state.uploadProgress = '';
        state.error = action.payload as string;
      })
      // Delete
      .addCase(deleteDocument.fulfilled, (state, action) => {
        state.items = state.items.filter(doc => doc.id !== action.payload);
      });
  }
});

export const { setUploadProgress, clearDocError } = documentSlice.actions;
export default documentSlice.reducer;
