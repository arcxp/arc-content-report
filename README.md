# arc-content-report

## 📁 **Repository Structure**

### Core Scripts
- **`redirects_report/identify_redirects.py`** - Redirects report script
- **`redirects_report/parallel_processor.py`** - Parallel processing engine with worker optimization
- **`redirects_report/status_checker.py`** - Async HTTP status checking (200/404 validation)
- **`daterange_builder.py`** - Automatic date range splitting for API limits
- **`utils.py`** - Utility functions, logging, and timing decorators

### Configuration & Setup
- **`redirects_report/run_script.sh`** - Convenient shell script for running the redirects report script
- **`config.env`** - Template for API credentials (copy to .env)
- **`requirements.txt`** - Python dependencies
- **`.gitignore`** - Prevents committing sensitive files and test outputs

### Documentation
- **`redirects_report/README.md`** - Redirects report documentation and usage guide
- **`README.md`** - This file

### Testing
- **`tests/test_daterange_builder.py`** - Unit tests for date range functionality

### Directories
- **`logs/`** - Log files (auto-created, gitignored)
- **`spreadsheets/`** - Output CSV files (auto-created, gitignored)

### New Features
- **Automatic Worker Optimization**: Dynamic scaling based on performance
- **Comprehensive Logging**: Detailed performance monitoring and error tracking
- **Unit Testing**: Comprehensive test coverage for all components
- **Environment Configuration**: Secure credential management
- **Parallel Processing**: Fast API calls with configurable worker pools
- **Async Status Checking**: Fast HTTP status validation

## 🔧 **Usage**

### Prerequisites
- Python 3.9+
- Arc XP API credentials

### Local Development Setup

1. **Clone and setup environment**:
```bash
cd arc-content-report
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
2. Copy credentials: `cp config.env .env`
3. Edit `.env` with your API credentials
4. Run redirects report: See `redirects_report/README.md`
5. Run wires report: TBD
6. Run images report: TBD

## 📄 License

This project is proprietary to Arc XP. All rights reserved. 