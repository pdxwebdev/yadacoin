# Running a YadaCoin Node on Android

This guide walks you through running a full YadaCoin node on an Android device using **Termux** and **QEMU** to emulate an Alpine Linux environment.

---

## Requirements

- Android 8.0 or later
- At least **4 GB RAM** (8 GB recommended)
- At least **20 GB free storage**
- [F-Droid](https://f-droid.org/) (recommended) or Google Play Store

---

## Step 1: Install Termux

Install Termux from F-Droid (preferred — the Play Store version is outdated):

1. Download and install [F-Droid](https://f-droid.org/F-Droid.apk)
2. Open F-Droid, search for **Termux**, and install it
3. Open Termux and run:

```sh
pkg update && pkg upgrade -y
```

---

## Step 2: Install QEMU in Termux

Install the QEMU system emulator package:

```sh
pkg install -y qemu-system-x86-64-headless
```

> **Note:** `qemu-system-x86-64-headless` is the version without a display requirement, suitable for running in Termux without a desktop environment.

---

## Step 3: Download the Alpine Linux ISO

Download the Alpine Linux "virtual" ISO (optimized for VMs):

```sh
mkdir -p ~/alpine-vm
cd ~/alpine-vm
curl -O https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/alpine-virt-$(curl -s https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/latest-releases.yaml | grep -m1 'version:' | awk '{print $2}').iso
```

Or manually check https://alpinelinux.org/downloads/ for the latest **x86_64 Virtual** ISO and download it:

```sh
curl -O https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/alpine-virt-3.21.0-x86_64.iso
```

> Replace `3.21.0` with the current latest version shown on the Alpine downloads page.

---

## Step 4: Create a Virtual Disk

Create a disk image to install Alpine onto:

```sh
cd ~/alpine-vm
qemu-img create -f qcow2 alpine-disk.qcow2 15G
```

---

## Step 5: Boot the Alpine Installer

Launch QEMU with the Alpine ISO to perform the initial install:

```sh
qemu-system-x86_64 \
  -m 2048 \
  -smp 2 \
  -drive file=alpine-disk.qcow2,format=qcow2 \
  -cdrom alpine-virt-*.iso \
  -boot d \
  -nographic \
  -net nic \
  -net user,hostfwd=tcp::8001-:8001,hostfwd=tcp::27017-:27017
```

At the Alpine boot prompt:

1. Log in as `root` (no password)
2. Run the setup wizard:

```sh
setup-alpine
```

Follow the prompts:

- **Keyboard layout:** `us` / `us`
- **Hostname:** anything (e.g. `yadanode`)
- **Network:** `eth0`, DHCP, no manual config
- **Root password:** set a strong password
- **Timezone:** your timezone
- **Proxy:** none
- **NTP:** `chrony` (default)
- **Mirror:** pick the fastest or use `1` (default)
- **SSH:** `openssh`
- **Disk:** `sda`, use `sys` layout, confirm with `y`

After install completes:

```sh
poweroff
```

---

## Step 6: Boot Alpine from the Installed Disk

Now boot without the ISO (remove the `-cdrom` and `-boot d` flags):

```sh
qemu-system-x86_64 \
  -m 2048 \
  -smp 2 \
  -drive file=alpine-disk.qcow2,format=qcow2 \
  -nographic \
  -net nic \
  -net user,hostfwd=tcp::8001-:8001,hostfwd=tcp::27017-:27017
```

Log in as `root` with the password you set during setup.

---

## Step 7: Run the YadaCoin Node Setup Script

Inside the Alpine VM, run the one-liner setup script:

```sh
curl -fsSL https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/yadanodesetup-alpine.sh | sh
```

The script will:

1. Install Python, curl, git, and OpenRC
2. Prompt you to install Docker (requires enabling the community repository)
3. Clone the YadaCoin repository to `/etc/yadacoin`
4. Download blockchain bootstrap data
5. Register and start the `yadanodemanager` OpenRC service

When prompted about Docker installation, enter `y` to enable the community repo and install it automatically.

---

## Step 8: Check Node Status

Once the script completes, monitor the node:

```sh
rc-service yadanodemanager status
```

Bootstrap data installation runs in the background and may take several minutes. Once complete, the node starts automatically.

---

## Step 9: Access the Node Web Interface

The QEMU port forwarding set up in Step 6 maps port `8001` from the VM to your Android device's `localhost`. Open a browser on your Android device and navigate to:

```
http://localhost:8001
```

---

## Tips

- **Keep the session alive:** Use `tmux` inside Termux (`pkg install tmux`) to keep QEMU running when you switch apps.
- **Persistent boot alias:** Add a shell alias to `~/.bashrc` in Termux for quick VM startup:
  ```sh
  echo "alias yadavm='qemu-system-x86_64 -m 2048 -smp 2 -drive file=\$HOME/alpine-vm/alpine-disk.qcow2,format=qcow2 -nographic -net nic -net user,hostfwd=tcp::8001-:8001'" >> ~/.bashrc
  ```
- **Resource usage:** QEMU is CPU-intensive. Charging your device during operation is recommended.
- **Storage:** The bootstrap download is several GB. Ensure you have sufficient space before starting.
