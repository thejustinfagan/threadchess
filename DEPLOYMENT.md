# Deployment Guide - Battle Dinghy Bot

This guide covers deploying the Battle Dinghy Twitter bot to cloud hosting platforms.

## Recommended Platforms

### Option 1: Railway (Easiest - Recommended)
- **Free tier**: $5 credit/month
- **Pros**: Easiest setup, automatic deployments from GitHub
- **Cons**: Requires credit card (but free tier is generous)

### Option 2: Render
- **Free tier**: Available but may sleep after inactivity
- **Pros**: True free tier, easy setup
- **Cons**: Free tier sleeps after 15 minutes of inactivity (not ideal for bots)

### Option 3: DigitalOcean App Platform
- **Pricing**: Starts at $5/month
- **Pros**: Reliable, good performance
- **Cons**: Paid only

## Deployment Steps

### Railway Deployment (Recommended)

1. **Sign up for Railway**
   - Go to https://railway.app
   - Sign up with GitHub (easiest)

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `battle_dinghy` repository

3. **Configure Environment Variables**
   - In Railway dashboard, go to your project
   - Click "Variables" tab
   - Add all variables from your `.env` file:
     ```
     X_API_KEY=your_api_key_here
     X_API_SECRET=your_api_secret_here
     X_ACCESS_TOKEN=your_access_token_here
     X_ACCESS_TOKEN_SECRET=your_access_token_secret_here
     BEARER_TOKEN=your_bearer_token_here
     SUPABASE_URL=your_supabase_url_here
     SUPABASE_KEY=your_supabase_anon_key_here
     ```

4. **Configure Service Type**
   - Railway should auto-detect the `Procfile`
   - Make sure it's set as a "Worker" service (not web service)
   - The bot doesn't need HTTP endpoints, just runs continuously

5. **Deploy**
   - Railway will automatically deploy from your GitHub repo
   - Check logs to verify it's running

### Render Deployment

1. **Sign up for Render**
   - Go to https://render.com
   - Sign up with GitHub

2. **Create New Background Worker**
   - Click "New +" → "Background Worker"
   - Connect your GitHub repository
   - Select `battle_dinghy` repo

3. **Configure Settings**
   - **Name**: `battle-dinghy-bot`
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: (leave blank)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main_polling.py`

4. **Add Environment Variables**
   - Scroll to "Environment Variables"
   - Add all variables from your `.env` file (same as Railway)

5. **Deploy**
   - Click "Create Background Worker"
   - Render will build and deploy
   - Check logs to verify it's running

### DigitalOcean App Platform

1. **Sign up for DigitalOcean**
   - Go to https://www.digitalocean.com
   - Create account

2. **Create App**
   - Go to App Platform
   - Click "Create App"
   - Connect GitHub repository
   - Select `battle_dinghy` repo

3. **Configure App**
   - **Resource Type**: Worker
   - **Build Command**: `pip install -r requirements.txt`
   - **Run Command**: `python main_polling.py`
   - **Environment**: Python 3.9

4. **Add Environment Variables**
   - Add all variables from your `.env` file

5. **Deploy**
   - Choose plan (Basic $5/month minimum)
   - Click "Create Resources"
   - Wait for deployment

## Post-Deployment Checklist

- [ ] Verify bot is running (check logs)
- [ ] Test by mentioning bot on Twitter
- [ ] Monitor logs for first few hours
- [ ] Set up log monitoring/alerts if available
- [ ] Verify Supabase connection is working
- [ ] Test a complete game flow

## Monitoring

### Railway
- View logs in Railway dashboard
- Set up alerts for errors

### Render
- View logs in Render dashboard
- Free tier: Check if worker is sleeping

### DigitalOcean
- View logs in App Platform dashboard
- Set up monitoring/alerts

## Troubleshooting

### Bot not responding
- Check logs for errors
- Verify environment variables are set correctly
- Check Twitter API credentials
- Verify Supabase connection

### Worker keeps restarting
- Check logs for crash errors
- Verify all dependencies are in `requirements.txt`
- Check Python version compatibility

### Rate limiting issues
- Bot polls every 60 seconds (should be fine)
- Check Twitter API rate limits in dashboard
- Monitor usage

## Cost Estimates

- **Railway**: ~$5-10/month (free tier covers most usage)
- **Render**: Free tier available (may sleep)
- **DigitalOcean**: $5/month minimum

## Security Notes

- Never commit `.env` file (already in `.gitignore`)
- Use environment variables in cloud platform
- Rotate API keys periodically
- Monitor for unauthorized access

## Updating the Bot

### Railway
- Push to GitHub → Automatic deployment

### Render
- Push to GitHub → Manual redeploy or auto-deploy if enabled

### DigitalOcean
- Push to GitHub → Automatic deployment

## Stopping the Bot

- Railway: Pause service in dashboard
- Render: Delete worker or pause
- DigitalOcean: Stop app in dashboard

