<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['patient_id'])) {
    header("Location: login.php");
    exit();
}

$appointment_id = isset($_GET['id']) ? intval($_GET['id']) : 0;

if ($appointment_id == 0) {
    header("Location: my_appointments.php");
    exit();
}

$patient_id = $_SESSION['patient_id'];
$patient_name = $_SESSION['patient_name'];

$conn = getConnection();

// Get appointment details with doctor information
$stmt = $conn->prepare("
    SELECT a.*, d.specialization, d.consultation_fee, d.qualification, d.experience_years
    FROM appointments a
    JOIN doctors d ON a.doctor_id = d.doctor_id
    WHERE a.appointment_id = ? AND a.patient_id = ?
");
$stmt->bind_param("ii", $appointment_id, $patient_id);
$stmt->execute();
$appointment = $stmt->get_result()->fetch_assoc();

// Get patient details
$patient_stmt = $conn->prepare("SELECT * FROM patients WHERE patient_id = ?");
$patient_stmt->bind_param("i", $patient_id);
$patient_stmt->execute();
$patient = $patient_stmt->get_result()->fetch_assoc();

$conn->close();

if (!$appointment) {
    header("Location: my_appointments.php");
    exit();
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Appointment Details - SCIS Hospital</title>
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
        
        .container {
            max-width: 800px;
            margin: 50px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 0 30px rgba(0,0,0,0.2);
        }
        
        h2 {
            color: #1e3a5f;
            text-align: center;
            margin-bottom: 25px;
            padding-bottom: 10px;
            border-bottom: 2px solid #2a7de1;
        }
        
        .section {
            margin-bottom: 25px;
        }
        
        .section-title {
            background: #2a7de1;
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 18px;
        }
        
        .detail-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
        }
        
        .detail-row {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            flex-wrap: wrap;
        }
        
        .detail-row:last-child {
            border-bottom: none;
        }
        
        .detail-label {
            font-weight: bold;
            color: #2a7de1;
            width: 180px;
            flex-shrink: 0;
        }
        
        .detail-value {
            color: #333;
            flex: 1;
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }
        
        .status-scheduled { background: #ffc107; color: #333; }
        .status-confirmed { background: #17a2b8; color: white; }
        .status-completed { background: #28a745; color: white; }
        .status-cancelled { background: #dc3545; color: white; }
        .status-no_show { background: #6c757d; color: white; }
        
        .urgency-badge {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .urgency-low { background: #28a745; color: white; }
        .urgency-medium { background: #ffc107; color: #333; }
        .urgency-high { background: #ff9800; color: white; }
        .urgency-critical { background: #dc3545; color: white; }
        
        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 25px;
            justify-content: center;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s;
            border: none;
            cursor: pointer;
            display: inline-block;
        }
        
        .btn-back {
            background: #6c757d;
            color: white;
        }
        
        .btn-back:hover {
            background: #5a6268;
        }
        
        .btn-cancel {
            background: #dc3545;
            color: white;
        }
        
        .btn-cancel:hover {
            background: #c82333;
        }
        
        .btn-book {
            background: #28a745;
            color: white;
        }
        
        .btn-book:hover {
            background: #1e7e34;
        }
        
        .btn-print {
            background: #17a2b8;
            color: white;
        }
        
        .btn-print:hover {
            background: #138496;
        }
        
        .warning-box {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }
        
        .info-box {
            background: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 20px;
                padding: 20px;
            }
            .detail-label {
                width: 100%;
                margin-bottom: 5px;
            }
            .detail-row {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>

<div class="container">
    <h2>📋 Appointment Details</h2>
    
    <!-- Appointment Information -->
    <div class="section">
        <div class="section-title">Appointment Information</div>
        <div class="detail-card">
            <div class="detail-row">
                <span class="detail-label">Appointment ID:</span>
                <span class="detail-value">#<?php echo $appointment['appointment_id']; ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Date:</span>
                <span class="detail-value"><?php echo date('l, d F Y', strtotime($appointment['appointment_date'])); ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Time:</span>
                <span class="detail-value"><?php echo date('g:i A', strtotime($appointment['appointment_time'])); ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span class="detail-value">
                    <span class="status-badge status-<?php echo $appointment['status']; ?>">
                        <?php echo ucfirst(str_replace('_', ' ', $appointment['status'])); ?>
                    </span>
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Urgency Level:</span>
                <span class="detail-value">
                    <span class="urgency-badge urgency-<?php echo $appointment['urgency_level']; ?>">
                        <?php echo ucfirst($appointment['urgency_level']); ?>
                    </span>
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Symptoms Description:</span>
                <span class="detail-value"><?php echo nl2br(htmlspecialchars($appointment['symptoms_description'])) ?: 'Not specified'; ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Booked On:</span>
                <span class="detail-value"><?php echo date('d M Y, h:i A', strtotime($appointment['created_at'])); ?></span>
            </div>
            <?php if ($appointment['cancelled_at']): ?>
            <div class="detail-row">
                <span class="detail-label">Cancelled On:</span>
                <span class="detail-value"><?php echo date('d M Y, h:i A', strtotime($appointment['cancelled_at'])); ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Cancellation Reason:</span>
                <span class="detail-value"><?php echo htmlspecialchars($appointment['cancellation_reason']) ?: 'Not specified'; ?></span>
            </div>
            <?php endif; ?>
        </div>
    </div>
    
    <!-- Doctor Information -->
    <div class="section">
        <div class="section-title">👨‍⚕️ Doctor Information</div>
        <div class="detail-card">
            <div class="detail-row">
                <span class="detail-label">Doctor ID:</span>
                <span class="detail-value"><?php echo $appointment['doctor_id']; ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Specialization:</span>
                <span class="detail-value"><?php echo htmlspecialchars($appointment['specialization']); ?></span>
            </div>
            <?php if ($appointment['qualification']): ?>
            <div class="detail-row">
                <span class="detail-label">Qualification:</span>
                <span class="detail-value"><?php echo htmlspecialchars($appointment['qualification']); ?></span>
            </div>
            <?php endif; ?>
            <?php if ($appointment['experience_years']): ?>
            <div class="detail-row">
                <span class="detail-label">Experience:</span>
                <span class="detail-value"><?php echo $appointment['experience_years']; ?> years</span>
            </div>
            <?php endif; ?>
            <?php if ($appointment['consultation_fee']): ?>
            <div class="detail-row">
                <span class="detail-label">Consultation Fee:</span>
                <span class="detail-value">₹<?php echo number_format($appointment['consultation_fee'], 2); ?></span>
            </div>
            <?php endif; ?>
        </div>
    </div>
    
    <!-- Patient Information -->
    <div class="section">
        <div class="section-title">👤 Patient Information</div>
        <div class="detail-card">
            <div class="detail-row">
                <span class="detail-label">Patient ID:</span>
                <span class="detail-value"><?php echo $patient['patient_id']; ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Full Name:</span>
                <span class="detail-value"><?php echo htmlspecialchars($patient['name']); ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Blood Group:</span>
                <span class="detail-value"><?php echo $patient['blood_group'] ?: 'Not recorded'; ?></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Emergency Contact:</span>
                <span class="detail-value"><?php echo $patient['emergency_contact_phone'] ?: 'Not recorded'; ?></span>
            </div>
        </div>
    </div>
    
    <!-- Important Notes -->
    <?php if ($appointment['status'] == 'scheduled' || $appointment['status'] == 'confirmed'): ?>
    <div class="info-box">
        <strong>📌 Please Note:</strong><br>
        • Please arrive 15 minutes before your appointment time.<br>
        • Bring any relevant medical reports or prescriptions.<br>
        • Carry your Patient ID for verification.<br>
        • To cancel or reschedule, please do so at least 2 hours in advance.
    </div>
    <?php endif; ?>
    
    <?php if ($appointment['status'] == 'cancelled'): ?>
    <div class="warning-box">
        <strong>⚠️ This appointment has been cancelled.</strong><br>
        You can book a new appointment using the button below.
    </div>
    <?php endif; ?>
    
    <!-- Action Buttons -->
    <div class="button-group">
        <a href="my_appointments.php" class="btn btn-back">← Back to Appointments</a>
        
        <?php if ($appointment['status'] == 'scheduled' || $appointment['status'] == 'confirmed'): ?>
            <form method="POST" action="my_appointments.php" onsubmit="return confirm('Are you sure you want to cancel this appointment?');" style="display: inline;">
                <input type="hidden" name="appointment_id" value="<?php echo $appointment['appointment_id']; ?>">
                <button type="submit" name="cancel_appointment" class="btn btn-cancel">Cancel Appointment</button>
            </form>
        <?php endif; ?>
        
        <a href="book_appointment.php" class="btn btn-book">📅 Book New Appointment</a>
        
        <a href="javascript:window.print()" class="btn btn-print">🖨️ Print Details</a>
    </div>
</div>

</body>
</html>