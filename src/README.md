# How to set this up on your own phone and computer

There are multiple steps to run this server properly

1) Go to CMD and type in `ipconfig`. Look under `IPv4 Address`. That is the web address we will be using.
2) Under `AirBrush/src` there are two files we need to run:
   1) `python serve_https.py` - runs the webpage so that your iPhone can use WebXR 
   2) `uvicorn server:app --host 0.0.0.0 --port 8081 --ssl-keyfile key.pem --ssl-certfile cert.pem` - this creates the websocket connection so the phone can continuously send information over
3) To run WebXR, we need to run on a secure web channel. To do that do the following:
   1) Go to Windows PowerShell and install `choco install mkcert`. 
   2) Then type `mkcert -install` (only need to do this once if doing it again) 
   3) Then use any terminal you want and go to `AirBrush/src`
   4) Then type `mkcert [IPv4 Address] localhost 127.0.0.1`
   5) This will create two files: `[IPv4 Address]+2.pem` and `[IPv4 Address]+2-key.pem`
   6) Rename those files to the following: 
    ```commandline
    copy "[IPv4 Address]+2.pem" cert.pem
    copy "[IPv4 Address]+2-key.pem" key.pem
    ```
   7) We now need to install the certificate onto the iPhone
      1) Type in `mkcert -CAROOT`. Inside that folder, there's a CA file (often `rootCA.pem`)
      2) Convert it to `.cer`: 
      ```commandline
      openssl x509 -in rootCA.pem -outform der -out rootCA.cer
      ```
      3) Download the `rootCa.cer` file onto your phone
      4) Open the file, it will prompt to install a profile
      5) Go to **Settings -> General -> VPN & Device Management -> install profile**
      6) Then go to **Settings -> General -> About -> Certificate Trust Settings**
      7) Enable **Full Trust**
   4) Now we can run WebXR. Type in the web address: 
      ```https://[IPv4 Address]:8443/phone_pose_stream.html```