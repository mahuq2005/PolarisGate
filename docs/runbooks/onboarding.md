# PolarisGate On-Prem — Team Onboarding Guide

## Step 1: Create a Team
1. Navigate to Admin → Settings → Teams
2. Click Create Team, enter name, assign admin
3. Click Create

## Step 2: Set Budget & Quotas
1. Navigate to Policy → Cost Center → Create Budget
2. Enter monthly budget (USD), alert threshold (80%), hard cutoff (ON)
3. Set webhook URL for Slack/Teams notifications

## Step 3: Assign LLM Providers
1. Admin → Settings → LLM Providers
2. Toggle providers, set rate limits per team

## Step 4: Create Users
1. Admin → Users → Create User
2. Assign role (Admin/Safety Officer/Viewer) and team

## Monitoring
- Dashboard: trace counts, toxicity/PII flags
- Cost Center: spend vs budget, anomaly detection
- Agents: manage team agents and MCP servers
