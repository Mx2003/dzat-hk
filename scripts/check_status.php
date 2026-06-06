<?php
require_once "/var/www/html/bootstrap.php";
use Espo\Core\Application;
$app = new Application();
$pdo = $app->getContainer()->get("entityManager")->getPDO();

echo "=== User Teams ===\n";
$stmt = $pdo->query("SELECT u.user_name, t.name as tname FROM user u JOIN team_user tu ON u.id=tu.user_id JOIN team t ON t.id=tu.team_id");
while ($row = $stmt->fetch()) echo "  {$row['user_name']} -> {$row['tname']}\n";

echo "\n=== User Roles ===\n";
$stmt = $pdo->query("SELECT u.user_name, r.name as rname FROM user u JOIN role_user ru ON u.id=ru.user_id JOIN role r ON r.id=ru.role_id");
while ($row = $stmt->fetch()) echo "  {$row['user_name']} -> {$row['rname']}\n";

echo "\n=== User Types ===\n";
$stmt = $pdo->query("SELECT user_name, type FROM user");
while ($row = $stmt->fetch()) echo "  {$row['user_name']} type={$row['type']}\n";

echo "\n=== Lead Status ===\n";
$assigned = $pdo->query("SELECT COUNT(*) FROM lead WHERE assigned_user_id IS NOT NULL")->fetchColumn();
$unassigned = $pdo->query("SELECT COUNT(*) FROM lead WHERE assigned_user_id IS NULL")->fetchColumn();
echo "  Assigned: $assigned\n";
echo "  Unassigned: $unassigned\n";
