<?php
require_once 'config.php';
session_start();

// Redirect if not logged in
if (!isset($_SESSION['patient_id'])) {
    header("Location: login.php");
    exit();
}

$suggested_doctor = "";
$suggested_specialization = "";
$symptoms = "";

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['analyze_symptoms'])) {
    $symptoms = strtolower(trim($_POST['symptoms']));
    
    // Symptom-to-specialization mapping (matching your doctors table)
    $symptom_map = [
        // Cardiology
        'chest pain' => 'Cardiologists',
        'heart pain' => 'Cardiologists',
        'palpitations' => 'Cardiologists',
        'difficulty breathing' => 'Cardiologists',
        'shortness of breath' => 'Cardiologists',
        
        // Neurology
        'brain' => 'Neurologists',
        'headache' => 'Neurologists',
        'severe headache' => 'Neurologists',
        'migraine' => 'Neurologists',
        'seizure' => 'Neurologists',
        'numbness' => 'Neurologists',
        'tingling' => 'Neurologists',
        'loss of consciousness' => 'Neurologists',
        'dizziness' => 'Neurologists',
        
        // Orthopedics
        'bone' => 'Orthopedics',
        'joint pain' => 'Orthopedics',
        'fracture' => 'Orthopedics',
        'back pain' => 'Orthopedics',
        'knee pain' => 'Orthopedics',
        'shoulder pain' => 'Orthopedics',
        
        // Dermatology
        'skin' => 'Dermatologists',
        'rash' => 'Dermatologists',
        'acne' => 'Dermatologists',
        'itching' => 'Dermatologists',
        
        // Gastroenterology
        'stomach' => 'Gastroenterologists',
        'abdomen' => 'Gastroenterologists',
        'digestion' => 'Gastroenterologists',
        'nausea' => 'Gastroenterologists',
        'vomiting' => 'Gastroenterologists',
        
        // Pediatrics
        'child' => 'Pediatricians',
        'baby' => 'Pediatricians',
        'infant' => 'Pediatricians',
        
        // General Medicine
        'fever' => 'General Physicians',
        'cold' => 'General Physicians',
        'cough' => 'General Physicians',
        'fatigue' => 'General Physicians',
        'weakness' => 'General Physicians'
    ];
    
    $matched_specialization = "General Physicians"; // default
    
    foreach ($symptom_map as $keyword => $specialization) {
        if (strpos($symptoms, $keyword) !== false) {
            $matched_specialization = $specialization;
            break;
        }
    }
    
    $suggested_specialization = $matched_specialization;
    
    $conn = getConnection();
    
    // Fetch a doctor with that specialization (case-insensitive match)
    $stmt = $conn->prepare("
        SELECT doctor_id, specialization 
        FROM doctors 
        WHERE LOWER(specialization) = LOWER(?) AND is_available = 1 
        LIMIT 1
    ");
    $stmt->bind_param("s", $matched_specialization);
    $stmt->execute();
    $result = $stmt->get_result();
    
    if ($row = $result->fetch_assoc()) {
        $suggested_doctor = $row['doctor_id'];
        $suggested_specialization = $row['specialization'];
    } else {
        // Try a LIKE query as fallback
        $stmt2 = $conn->prepare("
            SELECT doctor_id, specialization 
            FROM doctors 
            WHERE specialization LIKE ? AND is_available = 1 
            LIMIT 1
        ");
        $like_pattern = "%" . substr($matched_specialization, 0, -1) . "%"; // Remove 's' for plural
        $stmt2->bind_param("s", $like_pattern);
        $stmt2->execute();
        $result2 = $stmt2->get_result();
        
        if ($row2 = $result2->fetch_assoc()) {
            $suggested_doctor = $row2['doctor_id'];
            $suggested_specialization = $row2['specialization'];
        } else {
            $suggested_doctor = "No doctor available yet for this specialization. Please contact admin.";
        }
        $stmt2->close();
    }
    
    $stmt->close();
    $conn->close();
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Symptom Checker - SCIS Hospital</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .chatbot-container {
            max-width: 700px;
            margin: 50px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
        }
        .symptom-input {
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 15px 0;
            font-family: monospace;
        }
        .suggestion-box {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            border-left: 4px solid #2a7de1;
        }
        .book-btn {
            display: inline-block;
            background: #28a745;
            padding: 10px 20px;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 10px;
        }
        .book-btn:hover {
            background: #1e7e34;
        }
        .back-btn {
            display: inline-block;
            background: #6c757d;
            padding: 10px 20px;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 20px;
        }
        h2 {
            color: #1e3a5f;
        }
        .common-symptoms {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }
        .symptom-tag {
            display: inline-block;
            background: #e9ecef;
            padding: 5px 12px;
            border-radius: 20px;
            margin: 5px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .symptom-tag:hover {
            background: #2a7de1;
            color: white;
        }
        .available-doctors {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .doctor-list {
            list-style: none;
            padding: 0;
        }
        .doctor-list li {
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }
        .doctor-list li:last-child {
            border-bottom: none;
        }
        .direct-book {
            background: #17a2b8;
            margin-left: 10px;
            padding: 3px 10px;
            border-radius: 3px;
            font-size: 12px;
            color: white;
            text-decoration: none;
        }
    </style>
</head>
<body>
<div class="chatbot-container">
    <h2>🤖 Symptom Checker</h2>
    <p>Describe your symptoms in simple words. Our AI will suggest a specialist doctor.</p>
    
    <div class="common-symptoms">
        <strong>Common symptoms you can describe:</strong><br>
        <span class="symptom-tag" onclick="addSymptom('chest pain')">Chest pain</span>
        <span class="symptom-tag" onclick="addSymptom('severe headache')">Severe headache</span>
        <span class="symptom-tag" onclick="addSymptom('difficulty breathing')">Difficulty breathing</span>
        <span class="symptom-tag" onclick="addSymptom('stomach pain')">Stomach pain</span>
        <span class="symptom-tag" onclick="addSymptom('skin rash')">Skin rash</span>
        <span class="symptom-tag" onclick="addSymptom('joint pain')">Joint pain</span>
        <span class="symptom-tag" onclick="addSymptom('fever')">Fever</span>
        <span class="symptom-tag" onclick="addSymptom('numbness')">Numbness</span>
        <span class="symptom-tag" onclick="addSymptom('back pain')">Back pain</span>
        <span class="symptom-tag" onclick="addSymptom('nausea')">Nausea</span>
    </div>
    
    <form method="POST">
        <textarea name="symptoms" id="symptomsInput" class="symptom-input" rows="4" 
                  placeholder="Example: I have severe chest pain and difficulty breathing" required><?php echo htmlspecialchars($symptoms); ?></textarea>
        <button type="submit" name="analyze_symptoms" style="width:100%;">🔍 Analyze Symptoms</button>
    </form>
    
    <?php if ($suggested_doctor): ?>
        <div class="suggestion-box">
            <h3>🩺 Doctor Suggestion</h3>
            <p><strong>Based on your symptoms:</strong> <?php echo htmlspecialchars($symptoms); ?></p>
            <p><strong>Recommended Specialization:</strong> <?php echo htmlspecialchars($suggested_specialization); ?></p>
            <?php if (is_numeric($suggested_doctor)): ?>
                <p><strong>Suggested Doctor ID:</strong> <?php echo $suggested_doctor; ?></p>
                <a href="book_appointment.php?doctor_id=<?php echo $suggested_doctor; ?>" class="book-btn">📅 Book Appointment with this Doctor</a>
            <?php else: ?>
                <p style="color: #dc3545;"><?php echo $suggested_doctor; ?></p>
            <?php endif; ?>
        </div>
    <?php endif; ?>
    
    <!-- Show all available doctors -->
    <?php
    $conn = getConnection();
    $all_doctors = $conn->query("SELECT doctor_id, specialization, is_available FROM doctors WHERE is_available = 1 ORDER BY doctor_id");
    if ($all_doctors && $all_doctors->num_rows > 0):
    ?>
    <div class="available-doctors">
        <h3>👨‍⚕️ Available Doctors</h3>
        <ul class="doctor-list">
            <?php while($doc = $all_doctors->fetch_assoc()): ?>
            <li>
                <strong>Doctor ID: <?php echo $doc['doctor_id']; ?></strong> - <?php echo htmlspecialchars($doc['specialization']); ?>
                <a href="book_appointment.php?doctor_id=<?php echo $doc['doctor_id']; ?>" class="direct-book">Book Directly</a>
            </li>
            <?php endwhile; ?>
        </ul>
    </div>
    <?php endif; 
    $conn->close();
    ?>
    
    <a href="patient_dashboard.php" class="back-btn">← Back to Dashboard</a>
</div>

<script>
function addSymptom(symptom) {
    var textarea = document.getElementById('symptomsInput');
    var currentValue = textarea.value;
    if (currentValue) {
        textarea.value = currentValue + ', ' + symptom;
    } else {
        textarea.value = symptom;
    }
}
</script>
</body>
</html>