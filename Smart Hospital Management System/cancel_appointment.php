<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['patient_id'])) {
    header("Location: login.php");
    exit();
}

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['cancel'])) {
    $appointment_id = intval($_POST['appointment_id']);
    $patient_id = $_SESSION['patient_id'];
    
    $conn = getConnection();
    
    // Verify ownership before cancelling (using your column names)
    $stmt = $conn->prepare("
        UPDATE appointments 
        SET status = 'cancelled', 
            cancelled_at = NOW(),
            cancellation_reason = 'Cancelled by patient'
        WHERE appointment_id = ? AND patient_id = ? AND status IN ('scheduled', 'confirmed')
    ");
    $stmt->bind_param("ii", $appointment_id, $patient_id);
    
    if ($stmt->execute() && $stmt->affected_rows > 0) {
        $_SESSION['cancel_message'] = "Appointment cancelled successfully.";
        $_SESSION['cancel_type'] = "success";
    } else {
        $_SESSION['cancel_message'] = "Unable to cancel appointment. It may have already been completed or cancelled.";
        $_SESSION['cancel_type'] = "error";
    }
    
    $stmt->close();
    $conn->close();
}

header("Location: book_appointment.php");
exit();
?>