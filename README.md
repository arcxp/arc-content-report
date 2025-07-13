# arc-content-report

A suite of Python tools for analyzing and managing Arc XP content across multiple domains. This repository provides automated solutions for identifying redirects, analyzing unpublished wires content, and managing unused published photos in Photo Center. All modules feature parallel processing, rate limiting, and comprehensive logging for content analysis workflows.

## 📁 **Repository Structure**

### Core Scripts

#### Content Analysis Modules
- **`redirects_report/`** - Redirects analysis and HTTP status validation
  - `identify_redirects.py` - Identifies redirects within date ranges and validates HTTP status codes
  - `parallel_processor.py` - Optimized parallel processing engine with dynamic worker scaling
  - `status_checker.py` - Async HTTP status checking (200/404 validation) for redirect URLs

- **`wires_report/`** - Unpublished wires content analysis and cleanup
  - `identify_wires.py` - Identifies unpublished wires content for potential deletion
  - `parallel_processor.py` - Parallel processing engine with ElasticSearch query optimization

- **`images_report/`** - Photo Center unused published image analysis and management
  - `published_photo_analysis.py` - Analyzes published photos to identify unused images
  - `delete_or_expire_photos.py` - Deletes or expires photos from Photo Center
  - `create_lightbox_cache.py` - Creates SQLite cache of lightbox data for analysis of photo usage in lightboxes
  - `parallel_processor.py` - Parallel processing engine for photo operations

#### Shared Utilities
- **`daterange_builder.py`** - Automatic date range splitting for API rate limits
- **`utils.py`** - Shared utility functions, logging, rate limiting, and timing decorators

### Configuration & Setup
- **`config.env`** - Template for API credentials (copy to .env)
- **`requirements.txt`** - Python dependencies

### Documentation
- **`redirects_report/README.md`** - Redirects report documentation and usage guide
- **`wires_report/README.md`** - Unpublished wires articles report documentation and usage guide
- **`images_report/README.md`** - Unused published images report documentation and usage guide
- **`README.md`** - This file

### Testing

Run the test suite to verify the module is working correctly:

```bash
PYTHONPATH=. pytest tests/
# OR
python -m pytest tests/ -v 
```

### Directories
- **`logs/`** - Log files (auto-created, gitignored)
- **`spreadsheets/`** - Output CSV files (auto-created, gitignored)
- **`databases/`** - SQLlite databases (auto-created, gitignored)


### Features
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
5. Run wires report: See `wires_report/README.md`
6. Run images report: See `images_report/README.md`

### 🛠️ Running Modules in PyCharm (`-m` Flag Setup)

Using the PyCharm IDE allows you to set breakpoints to stop the code while it's running and examine the variables and their values that exist at the point in time. While not necessary for the function of these modules, it can be a useful development or debugging tool.

To run any module (e.g., `redirects_report.identify_redirects`, `wires_report.identify_wires`, or `images_report.published_photo_analysis`) with command-line arguments in PyCharm (using `python -m ...`), follow these steps:

1. **Open Run Configurations:**
   - In PyCharm, go to **`Run > Edit Configurations...`**.

2. **Create a New Configuration:**
   - Click the **`+`** icon at the top left and select **"Python"**.

3. **Configure the Module:**
   - **Name** the configuration something like: `Run [module_name]`.
   - **Select "Module name"** (not "Script path") and enter the module path:
     ```
     [module_name].[script_name]
     ```
     Example: `wires_report.identify_wires`
   - In the **"Parameters"** field, enter the command-line arguments you'd normally use.

4. **Set the Working Directory:**
   - Ensure the **working directory** is set to the project root (the directory containing the module packages).
   - This is especially important if your module uses relative file paths or expects certain files nearby.

5. **Save and Run:**
   - Click **Apply**, then **OK**.
   - Select your new configuration and click the green run arrow ▶️.

> 💡 **Why this is needed:**  
> Using the `-m` flag ensures the module is run in package context, which is important for relative imports. Running it this way also avoids issues with PyCharm injecting `--file` and other debug flags, which can break CLI tools using `argparse`.


## 📈 Monitoring and Logging

### Debug Mode
Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
```

### Log Levels
- `INFO`: General operation information
- `WARNING`: Non-critical issues
- `ERROR`: Critical errors requiring attention
- `DEBUG`: Detailed debugging information

### Performance Metrics
- Processing time per phase
- API call response times
- Memory usage statistics
- Worker utilization rates
- Success/failure rates
- Average time per item

## 📄 License

This project is proprietary to Arc XP. All rights reserved. 