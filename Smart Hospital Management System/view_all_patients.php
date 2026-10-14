<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['doctor_id'])) {
    header("Location: doctor.php");
    exit();
}

$doctor_id = $_SESSION['doctor_id'];
$search = isset($_GET['search']) ? $_GET['search'] : '';

$conn = getConnection();

// Get all patients who have appointments with this doctor
if ($search) {
    $patients = $conn->prepare("
        SELECT DISTINCT p.*, 
               COUNT(a.appointment_id) as total_visits,
               MAX(a.appointment_date) as last_visit
        FROM patients p
        JOIN appointments a ON p.patient_id = a.patient_id
        WHERE a.doctor_id = ? 
        AND (p.name LIKE ? OR p.patient_id LIKE ? OR p.emergency_contact_phone LIKE ?)
        GROUP BY p.patient_id
        ORDER BY last_visit DESC
    ");
    $search_param = "%$search%";
    $patients->bind_param("isss", $doctor_id, $search_param, $search_param, $search_param);
} else {
    $patients = $conn->prepare("
        SELECT DISTINCT p.*, 
               COUNT(a.appointment_id) as total_visits,
               MAX(a.appointment_date) as last_visit
        FROM patients p
        JOIN appointments a ON p.patient_id = a.patient_id
        WHERE a.doctor_id = ?
        GROUP BY p.patient_id
        ORDER BY last_visit DESC
    ");
    $patients->bind_param("i", $doctor_id);
}

$patients->execute();
$patients_result = $patients->get_result();
$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>My Patients - Doctor Dashboard</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .container {
            max-width: 1200px;
            margin: 30px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 25px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .search-box {
            padding: 10px;
            width: 300px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .search-btn {
            padding: 10px 20px;
            background: #2a7de1;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .patient-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .patient-table th, .patient-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .patient-table th {
            background: #2a7de1;
            color: white;
        }
        .patient-table tr:hover {
            background: #f5f5f5;
        }
        .view-btn {
            background: #28a745;
            color: white;
            padding: 5px 12px;
            text-decoration: none;
            border-radius: 4px;
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
        h2 {
            color: #1e3a5f;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h2>👥 My Patients</h2>
        <form method="GET" style="display: flex; gap: 10px;">
            <input type="text" name="search" class="search-box" placeholder="Search by name, ID, or phone" value="<?php echo htmlspecialchars($search); ?>">
            <button type="submit" class="search-btn">🔍 Search</button>
            <?php if ($search): ?>
                <a href="view_all_patients.php" class="search-btn" style="background: #6c757d;">Clear</a>
            <?php endif; ?>
        </form>
    </div>
    
    <?php if ($patients_result->num_rows > 0): ?>
        <table class="patient-table">
            <thead>
                <tr>
                    <th>Patient ID</th>
                    <th>Name</th>
                    <th>Blood Group</th>
                    <th>Phone</th>
                    <th>Total Visits</th>
                    <th>Last Visit</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                <?php while($patient = $patients_result->fetch_assoc()): ?>
                <tr>
                    <td><?php echo $patient['patient_id']; ?></td>
                    <td><?php echo htmlspecialchars($patient['name']); ?></td>
                    <td><?php echo $patient['blood_group']; ?></td>
                    <td><?php echo $patient['emergency_contact_phone']; ?></td>
                    <td><?php echo $patient['total_visits']; ?></td>
                    <td><?php echo $patient['last_visit'] ? date('d M Y', strtotime($patient['last_visit'])) : 'N/A'; ?></td>
                    <td>
                        <a href="view_patient_details.php?id=<?php echo $patient['patient_id']; ?>" class="view-btn">View Details</a>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p style="text-align: center; padding: 40px;">No patients found.</p>
    <?php endif; ?>
    
    <a href="doctor_dashboard.php" class="back-btn">← Back to Dashboard</a>
</div>
</body>
</html>