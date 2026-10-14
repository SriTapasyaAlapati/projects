<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['doctor_id'])) {
    header("Location: doctor.php");
    exit();
}

$patient_id = isset($_GET['id']) ? intval($_GET['id']) : 0;
$appointment_id = isset($_GET['appointment_id']) ? intval($_GET['appointment_id']) : 0;

if ($patient_id == 0) {
    header("Location: view_all_patients.php");
    exit();
}

$conn = getConnection();

// Get patient details
$patient_stmt = $conn->prepare("SELECT * FROM patients WHERE patient_id = ?");
$patient_stmt->bind_param("i", $patient_id);
$patient_stmt->execute();
$patient = $patient_stmt->get_result()->fetch_assoc();

// Get all appointments for this patient with this doctor
$appointments_stmt = $conn->prepare("
    SELECT a.*, d.specialization
    FROM appointments a
    JOIN doctors d ON a.doctor_id = d.doctor_id
    WHERE a.patient_id = ? AND a.doctor_id = ?
    ORDER BY a.appointment_date DESC, a.appointment_time DESC
");
$appointments_stmt->bind_param("ii", $patient_id, $_SESSION['doctor_id']);
$appointments_stmt->execute();
$appointments = $appointments_stmt->get_result();

// Get medical records for this patient
$records_stmt = $conn->prepare("
    SELECT * FROM medical_records 
    WHERE patient_id = ? AND doctor_id = ?
    ORDER BY uploaded_at DESC
");
$records_stmt->bind_param("ii", $patient_id, $_SESSION['doctor_id']);
$records_stmt->execute();
$records = $records_stmt->get_result();

$conn->close();

// Helper function to safely display values
function safe_value($value, $default = 'Not provided') {
    return !empty($value) ? htmlspecialchars($value) : $default;
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Patient Details - Doctor Dashboard</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .container {
            max-width: 1000px;
            margin: 30px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .patient-info {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        .info-item {
            padding: 10px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .info-label {
            font-weight: bold;
            color: #2a7de1;
            margin-bottom: 5px;
        }
        .info-value {
            color: #333;
        }
        .section {
            margin-top: 25px;
        }
        .section-title {
            font-size: 20px;
            color: #1e3a5f;
            border-bottom: 2px solid #2a7de1;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        .appointment-table, .records-table {
            width: 100%;
            border-collapse: collapse;
        }
        .appointment-table th, .appointment-table td,
        .records-table th, .records-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .appointment-table th, .records-table th {
            background: #2a7de1;
            color: white;
        }
        .appointment-table tr:hover, .records-table tr:hover {
            background: #f5f5f5;
        }
        .prescribe-btn {
            background: #28a745;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-top: 15px;
        }
        .prescribe-btn:hover {
            background: #1e7e34;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
        .back-btn:hover {
            background: #5a6268;
        }
        h2 {
            color: #1e3a5f;
        }
        h3 {
            color: #1e3a5f;
            margin-bottom: 15px;
        }
        .no-data {
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 5px;
            color: #666;
        }
        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }
        .status-scheduled { background: #ffc107; color: #333; }
        .status-confirmed { background: #17a2b8; color: white; }
        .status-completed { background: #28a745; color: white; }
        .status-cancelled { background: #dc3545; color: white; }
    </style>
</head>
<body>
<div class="container">
    <h2>👤 Patient Details</h2>
    
    <div class="patient-info">
        <h3>Personal Information</h3>
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Patient ID</div>
                <div class="info-value"><?php echo safe_value($patient['patient_id']); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Full Name</div>
                <div class="info-value"><?php echo safe_value($patient['name']); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Date of Birth</div>
                <div class="info-value">
                    <?php 
                    if (!empty($patient['date_of_birth']) && $patient['date_of_birth'] != '0000-00-00') {
                        echo date('d M Y', strtotime($patient['date_of_birth']));
                    } else {
                        echo 'Not provided';
                    }
                    ?>
                </div>
            </div>
            <div class="info-item">
                <div class="info-label">Blood Group</div>
                <div class="info-value"><?php echo safe_value($patient['blood_group'], 'Not recorded'); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Emergency Contact</div>
                <div class="info-value"><?php echo safe_value($patient['emergency_contact_phone']); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Emergency Contact Name</div>
                <div class="info-value"><?php echo safe_value($patient['emergency_contact_name']); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Address</div>
                <div class="info-value"><?php echo safe_value($patient['address']); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">City / State</div>
                <div class="info-value">
                    <?php 
                    $city = safe_value($patient['city'], '');
                    $state = safe_value($patient['state'], '');
                    echo trim($city . ' ' . $state) ?: 'Not provided';
                    ?>
                </div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h3 class="section-title">🏥 Medical Information</h3>
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Medical History</div>
                <div class="info-value"><?php echo safe_value($patient['medical_history'], 'None reported'); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Allergies</div>
                <div class="info-value"><?php echo safe_value($patient['allergies'], 'None reported'); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Current Medications</div>
                <div class="info-value"><?php echo safe_value($patient['current_medications'], 'None reported'); ?></div>
            </div>
            <div class="info-item">
                <div class="info-label">Registered On</div>
                <div class="info-value">
                    <?php 
                    if (!empty($patient['created_at'])) {
                        echo date('d M Y', strtotime($patient['created_at']));
                    } else {
                        echo 'Not available';
                    }
                    ?>
                </div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h3 class="section-title">📋 Appointment History</h3>
        <?php if ($appointments->num_rows > 0): ?>
            <table class="appointment-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Time</th>
                        <th>Doctor</th>
                        <th>Symptoms</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    <?php while($apt = $appointments->fetch_assoc()): ?>
                    <tr>
                        <td><?php echo date('d M Y', strtotime($apt['appointment_date'])); ?></td>
                        <td><?php echo date('g:i A', strtotime($apt['appointment_time'])); ?></td>
                        <td>Dr. <?php echo safe_value($apt['specialization']); ?></td>
                        <td><?php echo safe_value(substr($apt['symptoms_description'], 0, 50), 'No symptoms recorded'); ?></td>
                        <td>
                            <span class="status-badge status-<?php echo $apt['status']; ?>">
                                <?php echo ucfirst(str_replace('_', ' ', $apt['status'])); ?>
                            </span>
                        </td>
                        <td>
                            <?php if ($apt['status'] == 'scheduled' || $apt['status'] == 'confirmed'): ?>
                                <a href="upload_prescription.php?patient_id=<?php echo $patient_id; ?>&appointment_id=<?php echo $apt['appointment_id']; ?>" 
                                   style="background: #28a745; color: white; padding: 3px 8px; text-decoration: none; border-radius: 3px; font-size: 11px;">
                                    Prescribe
                                </a>
                            <?php endif; ?>
                        </td>
                    </tr>
                    <?php endwhile; ?>
                </tbody>
            </table>
        <?php else: ?>
            <div class="no-data">No appointment history found.</div>
        <?php endif; ?>
    </div>
    
    <div class="section">
        <h3 class="section-title">💊 Medical Records</h3>
        <?php if ($records->num_rows > 0): ?>
            <table class="records-table">
                <thead>
                    <tr>
                        <th>Record Type</th>
                        <th>Description</th>
                        <th>Uploaded On</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    <?php while($record = $records->fetch_assoc()): ?>
                    <tr>
                        <td><?php echo str_replace('_', ' ', ucfirst($record['record_type'])); ?></td>
                        <td><?php echo safe_value($record['description'], 'No description'); ?></td>
                        <td><?php echo date('d M Y, h:i A', strtotime($record['uploaded_at'])); ?></td>
                        <td>
                            <a href="<?php echo $record['file_path']; ?>" target="_blank" 
                               style="background: #17a2b8; color: white; padding: 3px 8px; text-decoration: none; border-radius: 3px; font-size: 11px;">
                                View File
                            </a>
                        </td>
                    </tr>
                    <?php endwhile; ?>
                </tbody>
            </table>
        <?php else: ?>
            <div class="no-data">No medical records found.</div>
        <?php endif; ?>
        
        <a href="upload_prescription.php?patient_id=<?php echo $patient_id; ?>" class="prescribe-btn">
            💊 Upload Prescription / Medical Record
        </a>
    </div>
    
    <a href="view_all_patients.php" class="back-btn">← Back to Patients List</a>
</div>
</body>
</html>