import os, uvicorn
from dotenv import load_dotenv
here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(here, "..", ".env"))
if __name__ == "__main__":
    uvicorn.run("main:app", app_dir=here, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5252")), proxy_headers=True)
