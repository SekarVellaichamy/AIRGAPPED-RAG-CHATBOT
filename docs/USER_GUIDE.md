# User Guide

Welcome to the **Isolated AI Chatbot**! This guide will help you get started and make the most of all features.

---

## Quick Reference

| Feature | How to Access |
|---------|---------------|
| Start New Chat | Click "New Chat" in sidebar |
| Upload Documents | Click upload icon (📎) in chat input |
| Policy Mode (RAG) | Select "Policy" mode before sending message |
| View Sources | Expand the "Sources" section in AI responses |
| Admin Panel | User dropdown → Admin Dashboard |

---

## 1. Getting Started

### Logging In

1. Navigate to the application URL (e.g., `http://localhost:5000`)
2. Enter your username and password
3. Click **Login**

> 💡 **First Time?** Default credentials are `admin` / `admin123`. Change your password immediately in the Admin Dashboard.

---

## 2. Chat Interface Overview

The interface has three main areas:

```
┌─────────────┬────────────────────────────────────┐
│             │                                    │
│  SIDEBAR    │         CHAT AREA                  │
│  (History)  │    (Conversation Display)          │
│             │                                    │
│ ○ New Chat  │                                    │
│ ○ Chat 1    │                                    │
│ ○ Chat 2    │                                    │
│             ├────────────────────────────────────┤
│             │  [Mode: General ▼]  [Type here...] │
└─────────────┴────────────────────────────────────┘
```

### Components

1. **Sidebar (Left)**: Lists your chat history. Click any session to resume it.
2. **Chat Area (Center)**: Shows the conversation with the AI.
3. **Input Box (Bottom)**: Where you type your messages.
4. **Mode Selector**: Switch between General and Policy modes.

---

## 3. Chat Modes

### General Mode
- Default conversation mode
- The AI responds using its built-in knowledge
- Great for open-ended questions and discussions

### Policy Mode (RAG)
- Uses your **uploaded documents** as knowledge source
- AI answers are grounded in your specific documents
- Shows **source citations** with relevance scores
- Best for policy questions, document lookups, and compliance queries

**When to use Policy Mode:**
- "What does our leave policy say about sick days?"
- "Summarize the key points from the uploaded handbook"
- "Find information about X in the documents"

---

## 4. Understanding AI Responses

### Streaming Responses
The AI types its answer in real-time, so you can start reading immediately.

### Thinking Mode (If Enabled)
Some configurations show the AI's reasoning in an expandable `<think>` section. This helps you understand how the AI arrived at its answer.

### Source Citations (Policy Mode)
When using Policy Mode, responses include:

- **Confidence Badge**: High/Medium/Low based on how relevant the sources are
- **Source Cards**: Expandable sections showing:
  - Document name and page number
  - Match percentage (relevance score)
  - Preview of the source text
  - Download button for the original file

---

## 5. Document Management

### Uploading Documents

1. Click the **Upload Icon** (📎) near the input box
2. Select one or more files (PDF, DOCX, TXT, MD)
3. Wait for the "Processing Complete" notification
4. Your documents are now indexed and available for Policy Mode queries

### Supported File Types

| Format | Extension |
|--------|-----------|
| PDF | `.pdf` |
| Microsoft Word | `.docx`, `.doc` |
| Plain Text | `.txt` |
| Markdown | `.md` |

> ⏱️ **Processing Time**: Large documents may take a few moments to parse and index.

---

## 6. Admin Dashboard

*Available to administrators only*

Access via the user dropdown menu (top right) → **Admin Dashboard**.

### Features

| Section | Description |
|---------|-------------|
| **Dashboard** | Overview statistics (users, documents, messages) |
| **User Management** | Create, edit, or delete user accounts |
| **File Management** | View, download, or delete uploaded documents |
| **Convert Tool** | Test document-to-markdown conversion |

---

## 7. Tips & Best Practices

### For Better RAG Results

1. **Be Specific**: Ask detailed questions for better document matching
2. **Use Keywords**: Include terms that appear in your documents
3. **Check Sources**: Always verify AI answers against the cited sources
4. **Upload Quality Docs**: Well-structured documents with clear headings work best

### Managing Sessions

- **Rename chats**: Right-click a session to rename it
- **Delete old chats**: Keep your sidebar organized by removing old sessions
- **Start fresh**: Use "New Chat" for unrelated topics

---

## 8. FAQ

**Q: Why is the AI not finding information from my documents?**
> Make sure you're in **Policy Mode** and that your documents have finished processing.

**Q: What does "Low Confidence" mean?**
> The AI found some relevant text, but it may not fully answer your question. Review the sources carefully.

**Q: Can I re-upload a document?**
> Yes, but delete the old version first to avoid duplicates.

**Q: How do I change my password?**
> Currently this must be done by an admin through the Admin Dashboard.
