# 🔐 Secure P2P Messenger with File Transfer

A secure peer-to-peer messenger with end-to-end encryption and file transfer capabilities, built with Python and modern web technologies.

## ✨ Features

### 🔒 Security
- **End-to-end encryption** using elliptic curve cryptography (ECDH)
- **Perfect forward secrecy** with ephemeral session keys
- **Digital signatures** for message authenticity
- **Onion routing** for enhanced privacy
- **Secure key exchange** with handshake protocol

### 💬 Messaging
- **Real-time P2P messaging** without central servers
- **Peer discovery** via UDP broadcast
- **Message delivery receipts** and read status
- **System notifications** for file transfers
- **Chat history** with local SQLite storage

### 📁 File Transfer
- **Secure file transfer** with encryption
- **Chunked uploads** for large files
- **Progress tracking** with real-time updates
- **File validation** with checksums
- **Auto-accept** for trusted peers
- **Transfer cancellation** support

### 🎨 User Interface
- **Modern responsive web interface**
- **Real-time updates** without page refresh
- **File preview** and progress bars
- **Mobile-friendly** design
- **Dark/Light theme** support

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip package manager
- OR Docker & Docker Compose (recommended for cross-platform compatibility)

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/MnM_HEX-TEAM.git
   cd MnM_HEX-TEAM
   ```

2. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

3. **Open your browser**
   Navigate to `http://localhost:8080`

4. **For testing P2P communication** (optional)
   ```bash
   docker-compose --profile testing up
   ```
   This will start a second instance at `http://localhost:8081`

### Option 2: Manual Python Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/MnM_HEX-TEAM.git
   cd MnM_HEX-TEAM
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the application**
   ```bash
   python3 run_server.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:8080`

## � Docker Deployment

### Why Use Docker?
- **Cross-platform compatibility** - Works on Windows, macOS, and Linux
- **Consistent environment** - No dependency conflicts between systems
- **Isolated dependencies** - Clean separation from host system
- **Easy deployment** - Single command to start the application

### Docker Commands

**Start the application:**
```bash
docker-compose up --build
```

**Run in background:**
```bash
docker-compose up -d --build
```

**Stop the application:**
```bash
docker-compose down
```

**View logs:**
```bash
docker-compose logs -f
```

**Testing P2P communication:**
```bash
docker-compose --profile testing up
```
This starts two instances:
- Instance 1: `http://localhost:8080`
- Instance 2: `http://localhost:8081`

### Docker Configuration

The project includes:
- `Dockerfile` - Multi-stage Python build with security optimizations
- `docker-compose.yml` - Service orchestration with networking
- `.dockerignore` - Excludes unnecessary files from build context

### Persistent Data

File uploads and downloads are persisted in:
- `./downloads/` - Received files
- `./uploads/` - Sent files

These directories are mounted as volumes and survive container restarts.

## �📖 Usage

### Basic Setup
1. **Choose a username** when prompted
2. **Connect to peers** on your local network
3. **Start chatting** securely

### File Sharing
1. **Click the attachment icon** 📎 in chat
2. **Select files** to upload
3. **Monitor progress** with real-time updates
4. **Files auto-download** for trusted peers

### Network Configuration
- **Default port**: 8080 (web), 8765 (P2P)
- **Discovery**: UDP broadcast on local network
- **Direct connection**: IP-to-IP messaging

## 🏗️ Architecture

### Backend (`/back`)
```
back/
├── main.py              # Core messenger logic
├── web.py               # Flask web server & API
├── core/
│   └── crypto.py        # Cryptographic engine
├── messaging/
│   └── handshake.py     # Peer handshake protocol
├── network/
│   ├── connection.py    # P2P connection manager
│   ├── onion_router.py  # Onion routing implementation
│   ├── file_transfer.py # Secure file transfer
│   └── protocols.py     # Message protocols
└── api/
    └── local_api.py     # Local API server
```

### Frontend (`/frontend`)
```
frontend/
├── index.html           # Main application page
├── login.html           # User authentication
├── css/
│   └── styles.css       # Modern responsive styles
└── js/
    └── app.js           # Interactive frontend logic
```

## 🔧 Configuration

### Environment Variables
```bash
export MESSENGER_USERNAME="your_username"  # Optional: Set default username
```

### Network Settings
Edit `run_server.py` to customize:
- Web server port
- P2P communication port
- File upload limits
- Discovery settings

## 🧪 Testing

### Run All Tests
```bash
python3 tests/run_all_tests.py
```

### Individual Test Suites
```bash
python3 tests/quick_test.py                    # Basic functionality
python3 tests/test_file_transfer.py            # File transfer system
python3 tests/test_comprehensive_p2p.py        # P2P integration
python3 tests/test_complete_file_transfer.py   # End-to-end transfer
```

### Test Coverage
- ✅ Cryptographic operations
- ✅ P2P messaging
- ✅ File transfer protocol
- ✅ Onion routing
- ✅ Web API endpoints
- ✅ Frontend integration

## 🔒 Security Details

### Cryptography
- **Curve**: secp256r1 (prime256v1)
- **Key exchange**: ECDH with HKDF
- **Encryption**: AES-256-GCM
- **Signatures**: ECDSA with SHA-256
- **Hashing**: SHA-256 for integrity

### Privacy Features
- **No central servers** - pure P2P
- **Onion routing** for IP protection
- **Ephemeral keys** for forward secrecy
- **Local storage only** - no cloud exposure

## 🌐 Network Protocol

### Message Types
- `HANDSHAKE_INIT` - Secure connection initiation
- `HANDSHAKE_RESPONSE` - Handshake completion
- `SECURE_MESSAGE` - Encrypted chat messages
- `FILE_OFFER` - File transfer proposal
- `FILE_CHUNK` - Encrypted file data
- `DELIVERY_RECEIPT` - Message acknowledgment

### Discovery Protocol
- UDP broadcast on local network
- Peer information exchange
- Automatic peer detection
- Device identification

## 📝 Development

### Adding Features
1. **Backend**: Extend `/back/network/` modules
2. **Frontend**: Modify `/frontend/js/app.js`
3. **API**: Add endpoints in `/back/web.py`
4. **Tests**: Create new test files in `/tests/`

### Code Style
- **Python**: PEP 8 compliant
- **JavaScript**: Modern ES6+ standards
- **CSS**: Responsive design with flexbox/grid
- **Documentation**: Comprehensive docstrings

## 🐛 Troubleshooting

### Common Issues

**Port already in use**
```bash
# Kill existing processes
lsof -ti:8080 | xargs kill -9
python3 run_server.py
```

**Firewall blocking**
- Allow ports 8080 and 8765
- Enable UDP broadcast for discovery

**Peers not discovered**
- Check network connectivity
- Verify same subnet
- Disable VPN if needed

**File transfer fails**
- Verify sufficient disk space
- Check file permissions
- Ensure stable connection

### Debug Mode
Enable debug logging:
```bash
export DEBUG=1
python3 run_server.py
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Cryptography**: Cryptography.io library
- **Web Framework**: Flask with CORS support
- **Frontend**: Vanilla JavaScript with modern APIs
- **Testing**: Custom test framework with comprehensive coverage

## 📞 Support

For issues and questions:
- Create GitHub issue
- Check troubleshooting section
- Review test cases for examples

---

**🔐 Secure P2P Messenger** - Communicate freely, securely, and without central control.
