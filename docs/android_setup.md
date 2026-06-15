# Running a YadaCoin Node on Android

To run a YadaCoin node on your Android device:

1. **Download Termux** from [F-Droid](https://f-droid.org/) (recommended) or Google Play Store
2. **Open Termux** and run the automated setup:

```sh
curl -fsSL https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/yadanodesetup.sh | sh
```

The setup script will automatically handle all configuration and startup. Bootstrap data downloads and installation run in the background—this may take several minutes. Once complete, your node will start automatically and be accessible on port 8001.

**Requirements:**

- Android 8.0 or later
- At least 4 GB RAM (8 GB recommended)
- At least 20 GB free storage
