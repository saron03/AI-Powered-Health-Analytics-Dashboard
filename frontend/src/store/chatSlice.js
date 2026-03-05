import { createSlice } from "@reduxjs/toolkit";

const initialState = {
  history: [],
  isLoading: false,
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    addMessage(state, action) {
      state.history.push(action.payload);
    },
    setLoading(state, action) {
      state.isLoading = action.payload;
    },
    resetChat(state) {
      state.history = [];
    },
  },
});

export const { addMessage, setLoading, resetChat } =
  chatSlice.actions;
export default chatSlice.reducer;