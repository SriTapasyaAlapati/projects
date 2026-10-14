<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['admin'])) {
    header("Location: admin_login.php");
    exit();
}

$message = "";
$type = "";

$conn = getConnection();

// ADD DOCTOR with positive ID validation
if (isset($_POST['add'])) {
    $doctor_id = $_POST['doctor_id'];
    $specialization = $_POST['specialization'];
    $password = $_POST['password'];
    
    // Validation for positive Doctor ID
    $errors = array();
    
    if (empty($doctor_id)) {
        $errors[] = "Doctor ID is required";
    } elseif (!is_numeric($doctor_id)) {
        $errors[] = "Doctor ID must be a number";
    } elseif ($doctor_id <= 0) {
        $errors[] = "Doctor ID must be a positive number (1, 2, 3, etc.)";
    } elseif ($doctor_id != floor($doctor_id)) {
        $errors[] = "Doctor ID must be a whole number (no decimals)";
    }
    
    if (empty($specialization)) {
        $errors[] = "Specialization is required";
    }
    
    if (empty($password)) {
        $errors[] = "Password is required";
    } elseif (strlen($password) < 4) {
        $errors[] = "Password must be at least 4 characters";
    }
    
    if (count($errors) > 0) {
        $message = implode("<br>", $errors);
        $type = "error";
    } else {
        $check = $conn->prepare("SELECT doctor_id FROM doctors WHERE doctor_id = ?");
        $check->bind_param("i", $doctor_id);
        $check->execute();
        $res = $check->get_result();
        
        if ($res->num_rows > 0) {
            $message = "Doctor ID already exists! Please use a different ID.";
            $type = "error";
        } else {
            $hashed_password = password_hash($password, PASSWORD_DEFAULT);
            
            $stmt = $conn->prepare("INSERT INTO doctors (doctor_id, specialization, password) VALUES (?, ?, ?)");
            $stmt->bind_param("iss", $doctor_id, $specialization, $hashed_password);
            
            if ($stmt->execute()) {
                $message = "Doctor added successfully with ID: " . $doctor_id;
                $type = "success";
            } else {
                $message = "Error adding doctor: " . $stmt->error;
                $type = "error";
            }
            $stmt->close();
        }
        $check->close();
    }
}

// DELETE DOCTOR
if (isset($_POST['delete'])) {
    $id = $_POST['doctor_id'];
    
    // Validate delete ID is positive
    if ($id > 0) {
        $stmt = $conn->prepare("DELETE FROM doctors WHERE doctor_id = ?");
        $stmt->bind_param("i", $id);
        
        if ($stmt->execute()) {
            $message = "Doctor deleted successfully!";
            $type = "success";
        } else {
            $message = "Error deleting doctor";
            $type = "error";
        }
        $stmt->close();
    } else {
        $message = "Invalid doctor ID for deletion";
        $type = "error";
    }
}

// Fetch all doctors
$result = $conn->query("SELECT * FROM doctors ORDER BY doctor_id");
?>

<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .container {
            max-width: 800px;
            margin: 50px auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #2a7de1;
            color: white;
        }
        .delete-form {
            display: inline;
        }
        .delete-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
        }
        .add-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
        }
        input {
            padding: 8px;
            margin: 5px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
        }
        .logout-link {
            display: inline-block;
            margin-top: 20px;
            color: #dc3545;
            text-decoration: none;
        }
        .error-msg {
            background: #ffebee;
            color: #c62828;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #c62828;
        }
        .success-msg {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #2e7d32;
        }
        .warning-text {
            font-size: 12px;
            color: #666;
            margin-top: -3px;
            margin-bottom: 10px;
        }
        input[type=number] {
            -moz-appearance: textfield;
        }
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button {
            opacity: 0.5;
        }
    </style>
</head>
<body>

<div class="container">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2>Admin Dashboard</h2>
        <a href="logout.php" class="logout-link">Logout</a>
    </div>

    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>

    <form method="POST">
        <h3>Add New Doctor</h3>
        
        <label>Doctor ID (Positive Number Only):</label>
        <input type="number" name="doctor_id" required min="1" step="1" value="1">
        <div class="warning-text">⚠️ Enter a positive whole number (1, 2, 3, ...). Zero and negative numbers are not allowed.</div>
        
        <label>Specialization:</label>
        <input type="text" name="specialization" required placeholder="e.g., Cardiologist, Neurologist">
        
        <label>Password:</label>
        <input type="password" name="password" required minlength="4">
        
        <button type="submit" name="add" class="add-btn">Add Doctor</button>
    </form>

    <hr>

    <h3>Existing Doctors</h3>
    
    <?php if ($result->num_rows > 0): ?>
        <table>
            <thead>
                <tr>
                    <th>Doctor ID</th>
                    <th>Specialization</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                <?php while($row = $result->fetch_assoc()): ?>
                <tr>
                    <td><?php echo $row['doctor_id']; ?></td>
                    <td><?php echo $row['specialization']; ?></td>
                    <td>
                        <form method="POST" class="delete-form" onsubmit="return confirm('Are you sure you want to delete Doctor ID <?php echo $row['doctor_id']; ?>?');">
                            <input type="hidden" name="doctor_id" value="<?php echo $row['doctor_id']; ?>">
                            <button type="submit" name="delete" class="delete-btn">Delete</button>
                        </form>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p style="text-align: center; padding: 20px; background: #f8f9fa; border-radius: 5px;">
            No doctors added yet. Use the form above to add doctors.
        </p>
    <?php endif; ?>
</div>

<script>
// Additional client-side validation for Doctor ID
document.querySelector('input[name="doctor_id"]').addEventListener('input', function() {
    var val = parseInt(this.value);
    if (val <= 0 || isNaN(val)) {
        this.setCustomValidity('Doctor ID must be a positive number (1, 2, 3, ...)');
    } else {
        this.setCustomValidity('');
    }
});
</script>

</body>
</html>