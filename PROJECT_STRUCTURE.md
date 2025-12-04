# SafeKeeping Flask App - Project Structure

This document provides a visual representation of the project's folder structure and descriptions of each component.

## Directory Tree

```
SafeKeeping_Flask__Render_app/
├── README.md                           # Project overview and setup instructions
├── lab10_flask_chartjs/                # Main application directory
│   ├── app.py                          # Flask application entry point and routes
│   ├── config.json                     # Configuration file (API keys, DB URLs, actuators)
│   ├── requirements.txt                # Python dependencies
│   ├── iot_data.db                     # SQLite database for IoT sensor data
│   ├── security_intrusions.db          # SQLite database for security events
│   │
│   ├── migrations/                     # Database migration scripts
│   │   └── init.sql                    # Initial database schema setup
│   │
│   ├── neon_db/                        # Neon PostgreSQL database data files
│   │   ├── envuronment_readings        # Environmental sensor readings data
│   │   └── intrusion_events            # Security intrusion events data
│   │
│   ├── static/                         # Static assets (CSS, JS, images)
│   │   └── style.css                   # Main stylesheet for the application
│   │
│   └── templates/                      # HTML Jinja2 templates
│       ├── base.html                   # Base template with common layout
│       ├── home.html                   # Home page dashboard
│       ├── environmental.html          # Environmental monitoring page
│       ├── manage_security.html        # Security management interface
│       ├── device_control.html         # IoT device control panel
│       └── about.html                  # About page
│
└── lab10_flask_chartjs.zip            # Archive of the application

```

## Component Descriptions

### Root Level
- **README.md**: Contains basic information about the project and its purpose for hosting on Render

### Application Directory (`lab10_flask_chartjs/`)

#### Core Files
- **app.py**: Main Flask application file containing:
  - Route definitions for web pages
  - API endpoints for sensor data ingestion
  - Database connection logic (PostgreSQL/Neon)
  - Integration with Adafruit IO (optional)
  
- **config.json**: Configuration file storing:
  - Adafruit IO credentials
  - Neon Database connection URL
  - Public Google Drive folder link
  - Actuator state definitions (LEDs, Buzzer, Servo, Camera)

- **requirements.txt**: Python package dependencies:
  - Flask (web framework)
  - psycopg2-binary (PostgreSQL adapter)
  - Adafruit-IO (IoT platform client)
  - chart.js (data visualization)

#### Database Files
- **iot_data.db**: SQLite database for local IoT sensor data storage
- **security_intrusions.db**: SQLite database for security-related events

#### Directories

##### `migrations/`
Contains database migration scripts for setting up and updating database schemas.
- **init.sql**: Initial schema creation with tables for:
  - Temperature readings
  - Motion events
  - Actuator state
  - Sync metadata

##### `neon_db/`
Stores data files for Neon PostgreSQL database integration:
- **envuronment_readings**: Environmental sensor data (temperature, humidity)
- **intrusion_events**: Security intrusion detection events

##### `static/`
Static assets served by Flask:
- **style.css**: CSS stylesheet defining the visual appearance of the web interface

##### `templates/`
Jinja2 HTML templates for the web interface:
- **base.html**: Base template with navigation and common structure
- **home.html**: Dashboard landing page with overview
- **environmental.html**: Environmental monitoring with charts (temperature, humidity)
- **manage_security.html**: Security event management and monitoring
- **device_control.html**: Control panel for IoT actuators
- **about.html**: Information about the project

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Database**: 
  - PostgreSQL (Neon - cloud-hosted)
  - SQLite (local storage)
- **Frontend**: HTML, CSS, JavaScript (Chart.js for visualizations)
- **IoT Integration**: Adafruit IO platform
- **Deployment**: Render (cloud hosting platform)

## Application Features

1. **Environmental Monitoring**: Track and visualize temperature and humidity readings
2. **Security Management**: Monitor and manage intrusion detection events
3. **Device Control**: Control IoT actuators (LEDs, Buzzer, Servo, Camera)
4. **Data Visualization**: Interactive charts using Chart.js
5. **Cloud Integration**: Syncs with Neon PostgreSQL and Adafruit IO
6. **Image Storage**: Integration with Google Drive for captured images

## Data Flow

1. IoT sensors → API endpoints (`/api/sensor`)
2. Data stored in → SQLite (local) and PostgreSQL (Neon cloud)
3. Web interface → Queries databases and displays via templates
4. User actions → Updates actuator states via device control panel
5. Images → Uploaded to Google Drive and referenced in database

---

*Last Updated: 2025-12-04*
