This is an entry point for n8n to control pipeline workflow

So this is FastAPI server which is working through Docker. FastAPI is used as a transport lazyer only.

HTTP respones from n8n:

http://stage-service:8129/batches
http://stage-service:8129/batches/{id}/runs
http://stage-service:8129/batches/{id}/runs/{run}/stages/{stage}

app.py - check output from n8n and send facts only back.
            creates: batch, run. stage, scheduler.
            Prompts:	POST /prompt-inputs/resolve
            Health: 	GET /health


api_models.py - describes the form of each HTTP-response.