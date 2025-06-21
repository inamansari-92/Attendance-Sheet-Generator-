




import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, send_file, redirect, url_for
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
import calendar

app = Flask(__name__)

# Staff members
STAFF_MEMBERS = [
    "Ebad ur Rehman",
    "Inam ur Rehman Ansari", 
    "Talha Siddiqui",
    "Asad Anwar Khan"
]

# Points system configuration
POINTS_CONFIG = {
    'full_day_present': 10,      # Full day attendance (7.5+ hours)
    'half_day_present': 5,       # Half day attendance (4-7.4 hours)
    'early_arrival': 2,          # Arriving before 10:00 AM
    'late_arrival': -1,          # Arriving after 10:30 AM
    'overtime': 1,               # Per hour overtime (after 7.5 hours)
    'absent': -5,                # Absent without leave
    'punctuality_bonus': 5,      # Weekly bonus for no late arrivals
    'perfect_attendance': 20,    # Monthly bonus for perfect attendance
    'field_work': 10,            # Field work or warehouse counts as full day
}

# Database setup
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_name TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            entry_time TEXT,
            exit_time TEXT,
            duty_hours REAL DEFAULT 0,
            remarks TEXT,
            points INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(staff_name, date)
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    return conn

def is_sunday(date_str):
    """Check if given date is Sunday"""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    return date_obj.weekday() == 6  # 6 is Sunday

def calculate_duty_hours(entry_time, exit_time):
    """Calculate duty hours between entry and exit time"""
    if not entry_time or not exit_time:
        return 0
    
    try:
        entry = datetime.strptime(entry_time, '%H:%M')
        exit = datetime.strptime(exit_time, '%H:%M')
        
        # Handle overnight shifts
        if exit < entry:
            exit += timedelta(days=1)
        
        duration = exit - entry
        hours = duration.total_seconds() / 3600
        return round(hours, 2)
    except:
        return 0

def calculate_points(status, entry_time, exit_time, duty_hours, date_str):
    """Calculate points based on attendance and performance"""
    points = 0
    
    if status == 'absent':
        points += POINTS_CONFIG['absent']
        return points
    
    if status == 'field_work':
        points += POINTS_CONFIG['field_work']
        return points
    
    if status == 'present':
        # Base attendance points
        if duty_hours >= 7.5:
            points += POINTS_CONFIG['full_day_present']
        elif duty_hours >= 4:
            points += POINTS_CONFIG['half_day_present']
        
        # Timing-based points
        if entry_time:
            try:
                entry = datetime.strptime(entry_time, '%H:%M').time()
                early_time = datetime.strptime('10:00', '%H:%M').time()
                late_time = datetime.strptime('10:30', '%H:%M').time()
                
                if entry <= early_time:
                    points += POINTS_CONFIG['early_arrival']
                elif entry > late_time:
                    points += POINTS_CONFIG['late_arrival']
            except:
                pass
        
        # Overtime points
        if duty_hours > 7.5:
            overtime_hours = duty_hours - 7.5
            points += int(overtime_hours * POINTS_CONFIG['overtime'])
    
    return points

def get_attendance_for_date(date_str):
    """Get attendance for a specific date"""
    conn = get_db_connection()
    attendance = conn.execute(
        'SELECT staff_name, status, entry_time, exit_time, duty_hours, remarks, points FROM attendance WHERE date = ?',
        (date_str,)
    ).fetchall()
    conn.close()
    
    # Convert to dictionary
    attendance_dict = {}
    for row in attendance:
        attendance_dict[row['staff_name']] = {
            'status': row['status'],
            'entry_time': row['entry_time'] or '',
            'exit_time': row['exit_time'] or '',
            'duty_hours': row['duty_hours'] or 0,
            'remarks': row['remarks'] or '',
            'points': row['points'] or 0
        }
    return attendance_dict

def save_attendance(date_str, attendance_data):
    """Save attendance data for a date"""
    conn = get_db_connection()
    
    for staff_name, data in attendance_data.items():
        # Calculate duty hours - field work gets automatic 7.5 hours
        if data.get('status') == 'field_work':
            duty_hours = 7.5
        else:
            duty_hours = calculate_duty_hours(data.get('entry_time'), data.get('exit_time'))
        
        # Calculate points
        points = calculate_points(
            data.get('status'),
            data.get('entry_time'),
            data.get('exit_time'),
            duty_hours,
            date_str
        )
        
        conn.execute('''
            INSERT OR REPLACE INTO attendance 
            (staff_name, date, status, entry_time, exit_time, duty_hours, remarks, points) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            staff_name,
            date_str,
            data.get('status'),
            data.get('entry_time') if data.get('status') == 'present' else None,
            data.get('exit_time') if data.get('status') == 'present' else None,
            duty_hours,
            data.get('remarks'),
            points
        ))
    
    conn.commit()
    conn.close()

def get_monthly_stats(year, month):
    """Get monthly statistics for all staff"""
    conn = get_db_connection()
    
    # Get all attendance records for the month
    records = conn.execute('''
        SELECT staff_name, status, duty_hours, points, date
        FROM attendance 
        WHERE date LIKE ? AND status != 'absent'
        ORDER BY staff_name, date
    ''', (f'{year}-{month:02d}-%',)).fetchall()
    
    conn.close()
    
    stats = {}
    for staff in STAFF_MEMBERS:
        stats[staff] = {
            'total_points': 0,
            'total_hours': 0,
            'present_days': 0,
            'perfect_attendance': True,
            'late_arrivals': 0,
            'average_hours': 0,
            'performance_grade': 'N/A'
        }
    
    # Calculate basic stats
    for record in records:
        staff = record['staff_name']
        if staff in stats:
            stats[staff]['total_points'] += record['points'] or 0
            stats[staff]['total_hours'] += record['duty_hours'] or 0
            if record['status'] in ['present', 'field_work']:
                stats[staff]['present_days'] += 1
    
    # Check for perfect attendance and calculate bonuses
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    working_days = []
    current_day = first_day
    while current_day <= last_day:
        if current_day.weekday() != 6:  # Not Sunday
            working_days.append(current_day.strftime('%Y-%m-%d'))
        current_day += timedelta(days=1)
    
    for staff in STAFF_MEMBERS:
        if stats[staff]['present_days'] == len(working_days):
            stats[staff]['total_points'] += POINTS_CONFIG['perfect_attendance']
        
        if stats[staff]['present_days'] > 0:
            stats[staff]['average_hours'] = round(stats[staff]['total_hours'] / stats[staff]['present_days'], 2)
        
        # Calculate performance grade
        total_points = stats[staff]['total_points']
        if total_points >= 200:
            stats[staff]['performance_grade'] = 'Excellent'
        elif total_points >= 150:
            stats[staff]['performance_grade'] = 'Good'
        elif total_points >= 100:
            stats[staff]['performance_grade'] = 'Average'
        elif total_points >= 50:
            stats[staff]['performance_grade'] = 'Below Average'
        else:
            stats[staff]['performance_grade'] = 'Poor'
    
    return stats

def generate_daily_pdf(date_str):
    """Generate daily attendance PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.darkblue,
        alignment=1,
        spaceAfter=20
    )
    
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    formatted_date = date_obj.strftime('%B %d, %Y')
    
    title = Paragraph(f"Daily Attendance Report - {formatted_date}", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Get attendance data
    attendance_data = get_attendance_for_date(date_str)
    
    # Create table data
    table_data = [['Staff Member', 'Status', 'Entry Time', 'Exit Time', 'Duty Hours', 'Points', 'Remarks']]
    
    total_points = 0
    total_hours = 0
    present_count = 0
    
    for staff_name in STAFF_MEMBERS:
        data = attendance_data.get(staff_name, {})
        status = data.get('status', 'Not Recorded')
        entry_time = data.get('entry_time', '-')
        exit_time = data.get('exit_time', '-')
        duty_hours = data.get('duty_hours', 0)
        points = data.get('points', 0)
        remarks = data.get('remarks', '-')
        
        if status in ['present', 'field_work']:
            present_count += 1
            total_hours += duty_hours
            total_points += points
        
        if status == 'present':
            status_display = '✓ Office'
        elif status == 'field_work':
            status_display = '🌾 Field/Warehouse'
        elif status == 'absent':
            status_display = '✗ Absent'
        else:
            status_display = 'Not Recorded'
            
        hours_display = f"{duty_hours:.1f}h" if duty_hours > 0 else '-'
        points_display = f"{points:+d}" if points != 0 else '0'
        
        table_data.append([
            staff_name,
            status_display,
            entry_time,
            exit_time,
            hours_display,
            points_display,
            remarks[:30] + '...' if len(remarks) > 30 else remarks
        ])
    
    # Create table
    table = Table(table_data, colWidths=[2*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.6*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    story.append(table)
    story.append(Spacer(1, 30))
    
    # Summary
    summary_data = [
        ['Summary', 'Values'],
        ['Staff Present', f"{present_count}/{len(STAFF_MEMBERS)}"],
        ['Total Duty Hours', f"{total_hours:.1f} hours"],
        ['Total Points Earned', f"{total_points:+d}"],
        ['Average Hours per Person', f"{total_hours/present_count:.1f}h" if present_count > 0 else "0h"]
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    
    story.append(summary_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_monthly_pdf(year, month):
    """Generate monthly attendance PDF with detailed statistics"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkblue,
        alignment=1,
        spaceAfter=20
    )
    
    month_name = calendar.month_name[month]
    title = Paragraph(f"Monthly Attendance Report - {month_name} {year}", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Get monthly statistics
    monthly_stats = get_monthly_stats(year, month)
    
    # Monthly Summary Table
    story.append(Paragraph("<b>Monthly Performance Summary</b>", styles['Heading3']))
    story.append(Spacer(1, 10))
    
    summary_data = [['Staff Member', 'Present Days', 'Total Hours', 'Avg Hours/Day', 'Total Points', 'Grade']]
    
    for staff_name in STAFF_MEMBERS:
        stats = monthly_stats[staff_name]
        summary_data.append([
            staff_name,
            str(stats['present_days']),
            f"{stats['total_hours']:.1f}h",
            f"{stats['average_hours']:.1f}h",
            f"{stats['total_points']:+d}",
            stats['performance_grade']
        ])
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 30))
    
    # Detailed daily records for each staff member
    story.append(Paragraph("<b>Detailed Daily Records</b>", styles['Heading3']))
    story.append(Spacer(1, 15))
    
    # Get all working days in month
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    working_days = []
    current_day = first_day
    while current_day <= last_day:
        if current_day.weekday() != 6:  # Not Sunday
            working_days.append(current_day.strftime('%Y-%m-%d'))
        current_day += timedelta(days=1)
    
    # Get attendance data for all working days
    conn = get_db_connection()
    attendance_records = {}
    for day in working_days:
        day_attendance = conn.execute(
            'SELECT staff_name, status, entry_time, exit_time, duty_hours, points, remarks FROM attendance WHERE date = ?',
            (day,)
        ).fetchall()
        attendance_records[day] = {
            row['staff_name']: {
                'status': row['status'],
                'entry_time': row['entry_time'],
                'exit_time': row['exit_time'],
                'duty_hours': row['duty_hours'],
                'points': row['points'],
                'remarks': row['remarks']
            } for row in day_attendance
        }
    conn.close()
    
    # Create detailed table for each staff member
    for staff_name in STAFF_MEMBERS:
        story.append(Paragraph(f"<b>{staff_name}</b>", styles['Heading4']))
        story.append(Spacer(1, 8))
        
        # Create table data for this staff member
        table_data = [['Date', 'Status', 'Entry', 'Exit', 'Hours', 'Points', 'Remarks']]
        
        for day in working_days:
            day_obj = datetime.strptime(day, '%Y-%m-%d')
            formatted_date = day_obj.strftime('%d-%m')
            
            data = attendance_records[day].get(staff_name, {})
            status = data.get('status', 'Not Recorded')
            entry_time = data.get('entry_time', '-')
            exit_time = data.get('exit_time', '-')
            duty_hours = data.get('duty_hours', 0)
            points = data.get('points', 0)
            remarks = data.get('remarks', '-')
            
            if status == 'present':
                status_display = '✓ Office'
            elif status == 'field_work':
                status_display = '🌾 Field'
            elif status == 'absent':
                status_display = '✗ Absent'
            else:
                status_display = '-'
                
            hours_display = f"{duty_hours:.1f}" if duty_hours > 0 else '-'
            points_display = f"{points:+d}" if points != 0 else '0'
            remarks_short = remarks[:15] + '...' if len(remarks) > 15 else remarks
            
            table_data.append([
                formatted_date,
                status_display,
                entry_time,
                exit_time,
                hours_display,
                points_display,
                remarks_short
            ])
        
        # Create table
        table = Table(table_data, colWidths=[0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.6*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))
        
        story.append(table)
        story.append(Spacer(1, 15))
    
    # Points system explanation
    story.append(Paragraph("<b>Points System Explanation</b>", styles['Heading3']))
    story.append(Spacer(1, 10))
    
    points_explanation = [
        ['Activity', 'Points'],
        ['Full Day (7.5+ hours)', f'+{POINTS_CONFIG["full_day_present"]}'],
        ['Half Day (4-7.4 hours)', f'+{POINTS_CONFIG["half_day_present"]}'],
        ['Early Arrival (before 10:00 AM)', f'+{POINTS_CONFIG["early_arrival"]}'],
        ['Late Arrival (after 10:30 AM)', f'{POINTS_CONFIG["late_arrival"]}'],
        ['Overtime (per hour)', f'+{POINTS_CONFIG["overtime"]}'],
        ['Field Work/Warehouse', f'+{POINTS_CONFIG["field_work"]}'],
        ['Absent', f'{POINTS_CONFIG["absent"]}'],
        ['Perfect Monthly Attendance', f'+{POINTS_CONFIG["perfect_attendance"]}']
    ]
    
    points_table = Table(points_explanation, colWidths=[3*inch, 1*inch])
    points_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    story.append(points_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# Enhanced HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Staff Attendance Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 300;
        }
        
        .current-date {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        
        .content {
            padding: 40px;
        }
        
        .date-selector {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        
        .date-selector label {
            font-weight: 600;
            color: #2c3e50;
            margin-right: 15px;
        }
        
        .date-selector input {
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 16px;
            margin-right: 15px;
        }
        
        .btn {
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            margin: 5px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(52, 152, 219, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
        }
        
        .btn-success:hover {
            box-shadow: 0 10px 20px rgba(46, 204, 113, 0.3);
        }
        
        .attendance-grid {
            display: grid;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .staff-card {
            background: #f8f9fa;
            border: 2px solid #e0e0e0;
            border-radius: 15px;
            padding: 25px;
            transition: all 0.3s ease;
        }
        
        .staff-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.1);
        }
        
        .staff-name {
            font-size: 1.3rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 15px;
        }
        
        .attendance-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .attendance-options {
            display: flex;
            gap: 10px;
        }
        
        .radio-option {
            display: flex;
            align-items: center;
            padding: 8px 16px;
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }
        
        .radio-option:hover {
            border-color: #3498db;
        }
        
        .radio-option.selected {
            background: #3498db;
            color: white;
            border-color: #3498db;
        }
        
        .radio-option input {
            display: none;
        }
        
        .time-input {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .time-input label {
            font-weight: 600;
            color: #2c3e50;
            min-width: 80px;
        }
        
        .time-input input {
            padding: 8px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 14px;
            width: 100px;
        }
        
        .remarks-section {
            grid-column: 1 / -1;
            margin-top: 10px;
        }
        
        .remarks-section label {
            font-weight: 600;
            color: #2c3e50;
            display: block;
            margin-bottom: 5px;
        }
        
        .remarks-section textarea {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 14px;
            resize: vertical;
            min-height: 80px;
        }
        
        .duty-hours-display {
            background: #e8f5e8;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            font-weight: 600;
            color: #2c5530;
        }
        
        .points-display {
            background: #e8f0ff;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            font-weight: 600;
            color: #1e40af;
        }
        
        .reports-section {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin-top: 30px;
        }
        
        .reports-section h3 {
            color: #2c3e50;
            margin-bottom: 20px;
            font-size: 1.5rem;
        }
        
        .report-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .sunday-notice {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            color: #856404;
            font-size: 1.1rem;
        }
        
        .success-message {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            padding: 15px;
            border-radius: 10px;
            color: #155724;
            margin-bottom: 20px;
        }
        
        .points-info {
            background: #e3f2fd;
            border: 1px solid #bbdefb;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        
        .points-info h4 {
            color: #1565c0;
            margin-bottom: 15px;
        }
        
        .points-breakdown {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 10px;
            font-size: 14px;
            color: #1565c0;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .content {
                padding: 20px;
            }
            
            .attendance-row {
                grid-template-columns: 1fr;
            }
            
            .attendance-options {
                flex-direction: column;
            }
            
            .report-buttons {
                flex-direction: column;
            }
            
            .time-input {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Staff Attendance Management</h1>
            <div class="current-date">{{ current_date_formatted }}</div>
        </div>
        
        <div class="content">
            {% if success_message %}
            <div class="success-message">
                {{ success_message }}
            </div>
            {% endif %}
            
            <div class="points-info">
                <h4>🎯 Points System</h4>
                <div class="points-breakdown">
                    <div>✅ Full Day (7.5+ hrs): +10 points</div>
                    <div>⏰ Half Day (4-7.4 hrs): +5 points</div>
                    <div>🌅 Early Arrival (before 10 AM): +2 points</div>
                    <div>⏰ Late Arrival (after 10:30 AM): -1 point</div>
                    <div>💪 Overtime (per hour): +1 point</div>
                    <div>🌾 Field Work/Warehouse: +10 points</div>
                    <div>❌ Absent: -5 points</div>
                    <div>🏆 Perfect Monthly Attendance: +20 points</div>
                </div>
            </div>
            
            <div class="date-selector">
                <form method="GET">
                    <label for="selected_date">Select Date:</label>
                    <input type="date" id="selected_date" name="date" value="{{ selected_date }}" onchange="this.form.submit()">
                </form>
            </div>
            
            {% if is_sunday %}
            <div class="sunday-notice">
                <strong>Sunday - No Attendance Required</strong><br>
                Sundays are off days. Please select a different date.
            </div>
            {% else %}
            <form method="POST" action="/save_attendance">
                <input type="hidden" name="date" value="{{ selected_date }}">
                
                <div class="attendance-grid">
                    {% for staff in staff_members %}
                    <div class="staff-card">
                        <div class="staff-name">{{ staff }}</div>
                        
                        <div class="attendance-row">
                            <div class="attendance-options">
                                <label class="radio-option {% if attendance_data.get(staff, {}).get('status') == 'present' %}selected{% endif %}">
                                    <input type="radio" name="{{ staff }}_status" value="present" 
                                           {% if attendance_data.get(staff, {}).get('status') == 'present' %}checked{% endif %}
                                           onchange="toggleTimeInputs('{{ staff }}', 'present')">
                                    ✓ Office
                                </label>
                                <label class="radio-option {% if attendance_data.get(staff, {}).get('status') == 'field_work' %}selected{% endif %}">
                                    <input type="radio" name="{{ staff }}_status" value="field_work"
                                           {% if attendance_data.get(staff, {}).get('status') == 'field_work' %}checked{% endif %}
                                           onchange="toggleTimeInputs('{{ staff }}', 'field_work')">
                                    🌾 Field/Warehouse
                                </label>
                                <label class="radio-option {% if attendance_data.get(staff, {}).get('status') == 'absent' %}selected{% endif %}">
                                    <input type="radio" name="{{ staff }}_status" value="absent"
                                           {% if attendance_data.get(staff, {}).get('status') == 'absent' %}checked{% endif %}
                                           onchange="toggleTimeInputs('{{ staff }}', 'absent')">
                                    ✗ Absent
                                </label>
                            </div>
                            
                            <div class="duty-hours-display" id="{{ staff }}_hours_display">
                                Duty Hours: <span id="{{ staff }}_hours">{{ "%.1f"|format(attendance_data.get(staff, {}).get('duty_hours', 0)) }}</span>h
                            </div>
                        </div>
                        
                        <div class="attendance-row" id="{{ staff }}_time_inputs" style="{% if attendance_data.get(staff, {}).get('status') != 'present' %}display: none;{% endif %}">
                            <div class="time-input">
                                <label>Entry Time:</label>
                                <input type="time" name="{{ staff }}_entry_time" 
                                       value="{{ attendance_data.get(staff, {}).get('entry_time', '') }}"
                                       onchange="calculateHours('{{ staff }}')">
                            </div>
                            
                            <div class="time-input">
                                <label>Exit Time:</label>
                                <input type="time" name="{{ staff }}_exit_time" 
                                       value="{{ attendance_data.get(staff, {}).get('exit_time', '') }}"
                                       onchange="calculateHours('{{ staff }}')">
                            </div>
                        </div>
                        
                        <div class="points-display" id="{{ staff }}_points_display">
                            Points: <span id="{{ staff }}_points">{{ attendance_data.get(staff, {}).get('points', 0) }}</span>
                        </div>
                        
                        <div class="remarks-section">
                            <label>Remarks:</label>
                            <textarea name="{{ staff }}_remarks" placeholder="Enter any remarks or notes...">{{ attendance_data.get(staff, {}).get('remarks', '') }}</textarea>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                
                <button type="submit" class="btn btn-success">💾 Save Attendance</button>
            </form>
            {% endif %}
            
            <div class="reports-section">
                <h3>📊 Download Reports</h3>
                <div class="report-buttons">
                    <a href="/download_daily_pdf?date={{ selected_date }}" class="btn">
                        📄 Download Daily Report
                    </a>
                    <a href="/download_monthly_pdf?year={{ current_year }}&month={{ current_month }}" class="btn">
                        📊 Download Monthly Report
                    </a>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Points configuration (matches Python backend)
        const POINTS_CONFIG = {
            'full_day_present': 10,
            'half_day_present': 5,
            'early_arrival': 2,
            'late_arrival': -1,
            'overtime': 1,
            'absent': -5,
            'field_work': 10
        };

        function toggleTimeInputs(staffName, status) {
            const timeInputs = document.getElementById(staffName + '_time_inputs');
            const hoursDisplay = document.getElementById(staffName + '_hours_display');
            const hoursSpan = document.getElementById(staffName + '_hours');
            const pointsSpan = document.getElementById(staffName + '_points');
            
            if (status === 'present') {
                timeInputs.style.display = 'grid';
                hoursDisplay.style.display = 'block';
                calculateHours(staffName);
            } else if (status === 'field_work') {
                timeInputs.style.display = 'none';
                hoursDisplay.style.display = 'block';
                hoursSpan.textContent = '7.5';
                pointsSpan.textContent = POINTS_CONFIG.field_work;
            } else if (status === 'absent') {
                timeInputs.style.display = 'none';
                hoursDisplay.style.display = 'block';
                hoursSpan.textContent = '0.0';
                pointsSpan.textContent = POINTS_CONFIG.absent;
            }
        }

        function calculateHours(staffName) {
            const entryTime = document.querySelector(`input[name="${staffName}_entry_time"]`).value;
            const exitTime = document.querySelector(`input[name="${staffName}_exit_time"]`).value;
            const hoursSpan = document.getElementById(staffName + '_hours');
            const pointsSpan = document.getElementById(staffName + '_points');
            
            if (entryTime && exitTime) {
                const entry = new Date(`2000-01-01 ${entryTime}`);
                const exit = new Date(`2000-01-01 ${exitTime}`);
                
                let hours = (exit - entry) / (1000 * 60 * 60);
                if (hours < 0) hours += 24; // Handle overnight shifts
                
                hoursSpan.textContent = hours.toFixed(1);
                
                // Calculate points
                let points = 0;
                if (hours >= 7.5) {
                    points += POINTS_CONFIG.full_day_present;
                    if (hours > 7.5) {
                        points += Math.floor(hours - 7.5) * POINTS_CONFIG.overtime;
                    }
                } else if (hours >= 4) {
                    points += POINTS_CONFIG.half_day_present;
                }
                
                // Check for early/late arrival
                const entryHour = entry.getHours();
                const entryMinute = entry.getMinutes();
                const entryDecimal = entryHour + entryMinute / 60;
                
                if (entryDecimal <= 10.0) {  // Before 10:00 AM
                    points += POINTS_CONFIG.early_arrival;
                } else if (entryDecimal > 10.5) {  // After 10:30 AM
                    points += POINTS_CONFIG.late_arrival;
                }
                
                pointsSpan.textContent = points > 0 ? '+' + points : points;
            } else {
                hoursSpan.textContent = '0.0';
                pointsSpan.textContent = '0';
            }
        }

        // Add interactivity to radio options
        document.querySelectorAll('.radio-option').forEach(option => {
            option.addEventListener('click', function() {
                const input = this.querySelector('input');
                const staffName = input.name.replace('_status', '');
                const status = input.value;
                
                // Remove selected class from other options for this staff
                document.querySelectorAll(`input[name="${staffName}_status"]`).forEach(radio => {
                    radio.closest('.radio-option').classList.remove('selected');
                });
                
                // Add selected class to clicked option
                this.classList.add('selected');
                input.checked = true;
                
                // Toggle time inputs
                toggleTimeInputs(staffName, status);
            });
        });

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            {% for staff in staff_members %}
            const status = "{{ attendance_data.get(staff, {}).get('status', '') }}";
            if (status) {
                toggleTimeInputs('{{ staff }}', status);
            }
            {% endfor %}
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    today = datetime.now().strftime('%Y-%m-%d')
    selected_date = request.args.get('date', today)
    
    # Check if selected date is Sunday
    is_sunday_date = is_sunday(selected_date)
    
    # Get attendance data for selected date
    attendance_data = get_attendance_for_date(selected_date)
    
    # Format current date
    current_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
    current_date_formatted = current_date_obj.strftime('%A, %B %d, %Y')
    
    success_message = request.args.get('success')
    
    return render_template_string(HTML_TEMPLATE,
                                staff_members=STAFF_MEMBERS,
                                selected_date=selected_date,
                                current_date_formatted=current_date_formatted,
                                is_sunday=is_sunday_date,
                                attendance_data=attendance_data,
                                success_message=success_message,
                                current_year=datetime.now().year,
                                current_month=datetime.now().month)

@app.route('/save_attendance', methods=['POST'])
def save_attendance_route():
    date_str = request.form.get('date')
    
    # Don't save attendance for Sundays
    if is_sunday(date_str):
        return redirect(url_for('index', date=date_str))
    
    attendance_data = {}
    for staff in STAFF_MEMBERS:
        status = request.form.get(f'{staff}_status')
        entry_time = request.form.get(f'{staff}_entry_time')
        exit_time = request.form.get(f'{staff}_exit_time')
        remarks = request.form.get(f'{staff}_remarks')
        
        if status:
            attendance_data[staff] = {
                'status': status,
                'entry_time': entry_time if status == 'present' else None,
                'exit_time': exit_time if status == 'present' else None,
                'remarks': remarks or ''
            }
    
    save_attendance(date_str, attendance_data)
    
    return redirect(url_for('index', date=date_str, success='Attendance saved successfully with points calculated!'))

@app.route('/download_daily_pdf')
def download_daily_pdf():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if is_sunday(date_str):
        return "No attendance report available for Sundays", 400
    
    pdf_buffer = generate_daily_pdf(date_str)
    
    filename = f"attendance_daily_{date_str}.pdf"
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

@app.route('/download_monthly_pdf')
def download_monthly_pdf():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    pdf_buffer = generate_monthly_pdf(year, month)
    
    filename = f"attendance_monthly_{year}_{month:02d}.pdf"
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)


    