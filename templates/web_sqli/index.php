<?php
$conn = new mysqli("localhost", "root", "", "testdb");
if ($conn->connect_error) { die("Conexión fallida: " . $conn->connect_error); }

$id = $_GET['id'] ?? 1;
$sql = "SELECT * FROM users WHERE id = $id";
$result = $conn->query($sql);

while($row = $result->fetch_assoc()) {
    echo "Usuario: " . $row["username"] . " - Password: " . $row["password"] . "<br>";
}
$conn->close();
?>

