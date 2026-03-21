# Getting Your Gemini API Key

To use the AI Vision features of TradesdocAi, you need a Google Gemini API key.

## Steps to Get Gemini API Key

### 1. Visit Google AI Studio
Go to: https://makersuite.google.com/app/apikey
(or https://aistudio.google.com/app/apikey)

### 2. Sign In
- Sign in with your Google account
- If you don't have one, create a free Google account first

### 3. Create API Key
- Click on "Create API Key" button
- Select an existing Google Cloud project or create a new one
- Copy the generated API key

### 4. Configure TradesdocAi

Open `/app/backend/.env` file and update:
```
GEMINI_API_KEY=your-actual-api-key-here
```

### 5. Restart Backend
```bash
sudo supervisorctl restart backend
```

## Testing the API Key

You can test if your API key is working by:

1. Starting the application
2. Logging in and going to Settings
3. Completing your company profile
4. Creating a new shipment
5. Uploading a sample Purchase Order document
6. If the extraction works, your API key is configured correctly!

## Free Tier Limits

Google Gemini offers a generous free tier:
- 15 requests per minute
- 1,500 requests per day
- 1 million tokens per minute

This should be sufficient for small to medium export businesses.

## Troubleshooting

**Error: "Gemini API key not configured"**
- Make sure you've added the key to `/app/backend/.env`
- Restart the backend service after adding the key

**Error: "Invalid API key"**
- Double-check that you copied the complete key
- Ensure there are no extra spaces or quotes
- Try generating a new API key

**Error: "Quota exceeded"**
- You've hit the free tier limit
- Wait for the quota to reset (daily limits reset at midnight Pacific Time)
- Consider upgrading to a paid tier for higher limits

## Alternative: OpenAI API

If you prefer to use OpenAI's GPT-4 Vision instead of Gemini, you can modify the backend code to use OpenAI's API. The application is designed to be flexible with AI providers.

## Privacy & Data

- Your documents are sent to Google's Gemini API for processing
- Google's standard privacy policies apply
- For sensitive documents, consider setting up a private deployment with on-premise AI models
