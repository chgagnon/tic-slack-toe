# tic-slack-toe
Competitive tic tac toe app for Slack workspaces

# Config Variables
- SLACK_BOT_TOKEN
- SLACK_APP_TOKEN
- DATABASE_URL - set by Heroku, often updated while app is deployed
- PORT - set by Heroku, often updated while app is deployed

# Heroku Files
- `Procfile` - specifies command for app start-up
- `requirements.txt` - specifies Python packages to install when app is first deployed
- `.env` - contains environment variables that are used when running `heroku local`
  - this is included in `.gitignore` to avoid posting tokens to GitHub
  - since it's not possible to run the Slack app in testing mode and point it to
    a local server and then easily switch back to pointing to Heroku, local tetsing
    doesn't really work
