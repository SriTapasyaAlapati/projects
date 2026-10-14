<?php
require_once 'config.php';
session_start();

// Check if doctor is logged in
if (!isset($_SESSION['doctor_id'])) {
    header("Location: doctor.php");
    exit();
}

$doctor_id = $_SESSION['doctor_id'];
$message = "";
$type = "";

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['update_status'])) {
    $appointment_id = intval($_POST['appointment_id']);
    $new_status = $_POST['new_status'];
    
    $conn = getConnection();
    
    // Verify this appointment belongs to the logged-in doctor
    $check = $conn->prepare("
        SELECT appointment_id FROM appointments 
        WHERE appointment_id = ? AND doctor_id = ?
    ");
    $check->bind_param("ii", $appointment_id, $doctor_id);
    $check->execute();
    $check_result = $check->get_result();
    
    if ($check_result->num_rows > 0) {
        // Update the status
        $update = $conn->prepare("
            UPDATE appointments 
            SET status = ? 
            WHERE appointment_id = ?
        ");
        $update->bind_param("si", $new_status, $appointment_id);
        
        if ($update->execute()) {
            $_SESSION['status_message'] = "Appointment status updated to " . ucfirst(str_replace('_', ' ', $new_status));
            $_SESSION['status_type'] = "success";
        } else {
            $_SESSION['status_message'] = "Error updating appointment status";
            $_SESSION['status_type'] = "error";
        }
        $update->close();
    } else {
        $_SESSION['status_message'] = "You don't have permission to update this appointment";
        $_SESSION['status_type'] = "error";
    }
    
    $check->close();
    $conn->close();
}

header("Location: doctor_dashboard.php");
exit();
?>