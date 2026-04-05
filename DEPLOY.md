# Deployment

## Streamlit Community Cloud

This is the recommended deployment mode for mobile usage.

### Secrets

Add these in the Streamlit Cloud app secrets:

```toml
OPENAI_API_KEY = "your-real-key"
OPENAI_MODEL = "gpt-4o-mini"
ENABLE_DESKTOP_VIDEO_TOOLS = false
```

### Behavior in cloud mode

- Script generation works
- Image prompt generation works
- Upload package works
- PC-only image generation and Remotion render buttons are hidden

### Deploy steps

1. Push this repository to GitHub.
2. Create a new app in Streamlit Community Cloud.
3. Select `streamlit_app.py` as the main file.
4. Paste the secrets above into the app secrets panel.
5. Deploy.

## PC mode

For local PC use, keep `ENABLE_DESKTOP_VIDEO_TOOLS` enabled or unset.
Then the image generation and Remotion rendering buttons will stay available.

