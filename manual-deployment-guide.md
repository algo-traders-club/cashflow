# Manual Deployment Guide for Cashflow Trading Agent

## Prerequisites
- AWS account with access to Lightsail
- Docker image saved as cashflow-trading.tar

## Deployment Steps

1. **Create a Container Service**
   - Go to AWS Lightsail Console: https://console.aws.amazon.com/lightsail/
   - Click on 'Containers'
   - Click 'Create container service'
   - Select 'Micro' (micro_2_0) with 1 node
   - Name your service 'cashflow-trading'
   - Click 'Create'

2. **Upload Container Image**
   - After the service is created, click on it
   - Click 'Upload container image'
   - Upload the cashflow-trading.tar file
   - Wait for the upload to complete

3. **Create Deployment**
   - Click 'Create deployment'
   - Select the uploaded image
   - Set container name to 'cashflow-app'
   - Configure port 9001 as HTTP
   - Add environment variables:
     - CONFIG_FILE=config/enhanced_config.yaml
     - API_PORT=9001
   - Set the public endpoint to container 'cashflow-app', port 9001
   - Configure health check to path '/status'
   - Click 'Deploy'

4. **Access Your Trading Agent**
   Once deployed, your Cashflow Trading Agent will be available at the URL provided by Lightsail.
   
   API Endpoints:
   - Status: https://<your-lightsail-url>/status
   - Debug: https://<your-lightsail-url>/debug
   - Portfolio: https://<your-lightsail-url>/portfolio
   - Start Trading: https://<your-lightsail-url>/start (POST)
   - Stop Trading: https://<your-lightsail-url>/stop (POST)

## Monitoring and Management

- View logs: In the Lightsail console, select your container service and click on 'Logs'
- Restart: Click on 'Deployments' and then 'Create deployment' to redeploy
- Scale: Under 'Capacity' you can adjust the number of nodes

## Troubleshooting

- If the health check fails, verify that the application is running correctly by checking the logs
- Ensure the port and environment variables are correctly configured
- If needed, you can SSH into the container to debug by clicking on 'Connect'

