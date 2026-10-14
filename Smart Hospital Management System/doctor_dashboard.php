<?php
require_once 'config.php';
session_start();

// Check if doctor is logged in
if (!isset($_SESSION['doctor_id'])) {
    header("Location: doctor.php");
    exit();
}

$doctor_id = $_SESSION['doctor_id'];
$specialization = $_SESSION['doctor_specialization'];

$conn = getConnection();

// Get doctor's appointments for today (using correct column names)
$today = date('Y-m-d');
$appointments = $conn->prepare("
    SELECT a.*, p.name as patient_name, p.blood_group, p.emergency_contact_phone 
    FROM appointments a 
    JOIN patients p ON a.patient_id = p.patient_id 
    WHERE a.doctor_id = ? AND a.appointment_date = ?
    ORDER BY a.appointment_time
");
$appointments->bind_param("is", $doctor_id, $today);
$appointments->execute();
$today_appointments = $appointments->get_result();

// Get total patient count for this doctor
$patient_count = $conn->prepare("
    SELECT COUNT(DISTINCT patient_id) as total 
    FROM appointments WHERE doctor_id = ?
");
$patient_count->bind_param("i", $doctor_id);
$patient_count->execute();
$total_patients = $patient_count->get_result()->fetch_assoc();

// Get upcoming appointments count
$upcoming_count = $conn->prepare("
    SELECT COUNT(*) as total 
    FROM appointments 
    WHERE doctor_id = ? AND appointment_date >= CURDATE() AND status IN ('scheduled', 'confirmed')
");
$upcoming_count->bind_param("i", $doctor_id);
$upcoming_count->execute();
$upcoming_total = $upcoming_count->get_result()->fetch_assoc();

// Get completed appointments count
$completed_count = $conn->prepare("
    SELECT COUNT(*) as total 
    FROM appointments 
    WHERE doctor_id = ? AND status = 'completed'
");
$completed_count->bind_param("i", $doctor_id);
$completed_count->execute();
$completed_total = $completed_count->get_result()->fetch_assoc();

$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>Doctor Dashboard - SCIS Hospital</title>
    <link rel="stylesheet" href="style.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background-image: url("hospital.jpeg");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            font-family: Arial, Helvetica, sans-serif;
        }
        
        .dashboard-container {
            max-width: 1400px;
            margin: 30px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #2a7de1;
            padding-bottom: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        
        .header h1 {
            color: #1e3a5f;
            font-size: 28px;
        }
        
        .doctor-info {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            color: white;
        }
        
        .doctor-details {
            font-size: 16px;
        }
        
        .doctor-details p {
            margin: 5px 0;
        }
        
        .stats-container {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.2);
            padding: 15px 25px;
            border-radius: 8px;
            text-align: center;
            min-width: 120px;
            backdrop-filter: blur(10px);
        }
        
        .stat-number {
            font-size: 32px;
            font-weight: bold;
        }
        
        .stat-label {
            font-size: 12px;
            margin-top: 5px;
            opacity: 0.9;
        }
        
        .nav-buttons {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .nav-btn {
            background: #2a7de1;
            padding: 12px 25px;
            text-decoration: none;
            color: white;
            border-radius: 8px;
            display: inline-block;
            transition: all 0.3s;
            font-weight: bold;
        }
        
        .nav-btn:hover {
            background: #1f5fbf;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .nav-btn.emergency {
            background: #dc3545;
        }
        
        .nav-btn.emergency:hover {
            background: #c82333;
        }
        
        .section-title {
            margin-top: 30px;
            margin-bottom: 20px;
            color: #1e3a5f;
            font-size: 22px;
            border-left: 4px solid #2a7de1;
            padding-left: 15px;
        }
        
        .appointment-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .appointment-table th, .appointment-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .appointment-table th {
            background: #2a7de1;
            color: white;
            font-weight: bold;
        }
        
        .appointment-table tr:hover {
            background: #f5f5f5;
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .status-scheduled { background: #ffc107; color: #333; }
        .status-confirmed { background: #17a2b8; color: white; }
        .status-completed { background: #28a745; color: white; }
        .status-cancelled { background: #dc3545; color: white; }
        .status-no_show { background: #6c757d; color: white; }
        
        .logout-btn {
            background: #dc3545;
            padding: 10px 20px;
            text-decoration: none;
            color: white;
            border-radius: 5px;
            transition: all 0.3s;
        }
        
        .logout-btn:hover {
            background: #c82333;
        }
        
        .action-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .view-btn, .prescribe-btn, .update-status-btn {
            padding: 5px 12px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 12px;
            border: none;
            cursor: pointer;
        }
        
        .view-btn {
            background: #17a2b8;
            color: white;
        }
        
        .prescribe-btn {
            background: #28a745;
            color: white;
        }
        
        .update-status-btn {
            background: #ffc107;
            color: #333;
        }
        
        .status-select {
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid #ddd;
            font-size: 12px;
        }
        
        @media (max-width: 768px) {
            .dashboard-container {
                padding: 15px;
                margin: 15px;
            }
            .appointment-table {
                font-size: 12px;
            }
            .appointment-table th, .appointment-table td {
                padding: 8px;
            }
            .nav-buttons {
                flex-direction: column;
            }
            .nav-btn {
                text-align: center;
            }
            .action-buttons {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>

<div class="dashboard-container">
    <div class="header">
        <h1>🏥 Doctor Dashboard</h1>
        <a href="logout.php" class="logout-btn">🚪 Logout</a>
    </div>
    
    <div class="doctor-info">
        <div class="doctor-details">
            <p><strong>👨‍⚕️ Doctor ID:</strong> <?php echo htmlspecialchars($doctor_id); ?></p>
            <p><strong>📚 Specialization:</strong> <?php echo htmlspecialchars($specialization); ?></p>
        </div>
        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-number"><?php echo $total_patients['total']; ?></div>
                <div class="stat-label">Total Patients</div>
            </div>
            <div class="stat-card">
                <div class="stat-number"><?php echo $upcoming_total['total']; ?></div>
                <div class="stat-label">Upcoming</div>
            </div>
            <div class="stat-card">
                <div class="stat-number"><?php echo $completed_total['total']; ?></div>
                <div class="stat-label">Completed</div>
            </div>
        </div>
    </div>
    
    <div class="nav-buttons">
        <a href="view_all_patients.php" class="nav-btn">👥 View All Patients</a>
        <a href="manage_all_appointments.php" class="nav-btn">📅 Manage Appointments</a>
        <a href="upload_prescription.php" class="nav-btn">💊 Upload Prescription</a>
        <a href="update_availability.php" class="nav-btn">🟢 Update Availability</a>
    </div>
    
    <h3 class="section-title">📋 Today's Appointments (<?php echo date('d M Y', strtotime($today)); ?>)</h3>
    
    <?php if ($today_appointments->num_rows > 0): ?>
        <table class="appointment-table">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Patient Name</th>
                    <th>Blood Group</th>
                    <th>Contact</th>
                    <th>Urgency</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php while($apt = $today_appointments->fetch_assoc()): ?>
                <tr>
                    <td><?php echo date('g:i A', strtotime($apt['appointment_time'])); ?></td>
                    <td><?php echo htmlspecialchars($apt['patient_name']); ?></td>
                    <td><?php echo htmlspecialchars($apt['blood_group']); ?></td>
                    <td><?php echo htmlspecialchars($apt['emergency_contact_phone']); ?></td>
                    <td>
                        <span class="status-badge" style="background: <?php 
                            echo $apt['urgency_level'] == 'critical' ? '#dc3545' : 
                                ($apt['urgency_level'] == 'high' ? '#ff9800' : 
                                ($apt['urgency_level'] == 'medium' ? '#ffc107' : '#28a745')); 
                        ?>; color: white;">
                            <?php echo ucfirst($apt['urgency_level'] ?? 'low'); ?>
                        </span>
                    </span>
                    </td>
                    <td><span class="status-badge status-<?php echo $apt['status']; ?>"><?php echo ucfirst(str_replace('_', ' ', $apt['status'])); ?></span></td>
                    <td>
                        <div class="action-buttons">
                            <a href="view_patient_details.php?id=<?php echo $apt['patient_id']; ?>&appointment_id=<?php echo $apt['appointment_id']; ?>" class="view-btn">👁️ View</a>
                            <a href="upload_prescription.php?patient_id=<?php echo $apt['patient_id']; ?>&appointment_id=<?php echo $apt['appointment_id']; ?>" class="prescribe-btn">💊 Prescribe</a>
                        </div>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p style="text-align: center; padding: 40px; background: #f8f9fa; border-radius: 8px;">
            🎉 No appointments scheduled for today. Enjoy your day!
        </p>
    <?php endif; ?>
</div>

</body>
</html>