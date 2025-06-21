# Staff Attendance Management System

![Attendance Management](https://via.placeholder.com/800x400?text=Attendance+Management+System)

A comprehensive web application for tracking staff attendance, calculating performance points, and generating detailed reports with PDF export capabilities.

## Features

- **Daily Attendance Tracking**: Record staff attendance with office, field work, or absent statuses
- **Automated Points System**: Calculate performance points based on:
  - Punctuality (early/late arrivals)
  - Work duration (full/half day)
  - Overtime hours
  - Field work assignments
  - Perfect monthly attendance bonus
- **Reporting**:
  - Daily attendance reports with summary statistics
  - Monthly performance reports with detailed analytics
  - PDF export for both daily and monthly reports
- **User-Friendly Interface**: Intuitive web interface with real-time points calculation
- **Database Storage**: SQLite database for persistent data storage

## Technology Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite
- **PDF Generation**: ReportLab
- **Deployment**: Can be run locally or deployed to any Python-compatible hosting environment

## Installation

### Prerequisites
- Python 3.7+
- pip package manager

### Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/staff-attendance-system.git
   cd staff-attendance-system
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**:
   ```bash
   python app.py
   ```
   (The application will automatically create the database on first run)

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Access the application**:
   Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

### Daily Attendance
1. Select a date (non-Sunday) from the date picker
2. For each staff member:
   - Select attendance status: Office, Field/Warehouse, or Absent
   - For Office status, enter entry and exit times
   - Add any remarks if needed
3. Click "Save Attendance" to store the data

### Reports
- **Daily Report**: Shows attendance details for the selected date
- **Monthly Report**: Provides performance summary and detailed daily records for the month
- Both reports can be downloaded as PDF files

### Points System
The application calculates points based on:
- Full day (7.5+ hours): 10 points
- Half day (4-7.4 hours): 5 points
- Early arrival (before 10:00 AM): +2 points
- Late arrival (after 10:30 AM): -1 point
- Overtime (per hour): +1 point
- Field work: 10 points
- Absent: -5 points
- Perfect monthly attendance: +20 points bonus

## Screenshots

![Main Interface](https://via.placeholder.com/600x400?text=Main+Interface)
*Main attendance tracking interface*

![Daily Report](https://via.placeholder.com/600x400?text=Daily+Report)
*Sample daily attendance report*

![Monthly Report](https://via.placeholder.com/600x400?text=Monthly+Report)
*Sample monthly performance report*

## File Structure

```
staff-attendance-system/
├── app.py                 # Main application file
├── attendance.db          # Database file (created automatically)
├── requirements.txt       # Python dependencies
├── README.md              # This documentation file
└── static/                # Static assets (CSS, images)
└── templates/             # HTML templates
```

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository
2. Create a new branch for your feature (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For any issues or questions, please [open an issue](https://github.com/yourusername/staff-attendance-system/issues) on GitHub.
