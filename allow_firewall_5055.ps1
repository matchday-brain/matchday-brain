$ruleName = "Matchday Brain Flask 5055"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
  Write-Host "Firewall rule already exists: $ruleName" -ForegroundColor Green
} else {
  New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 5055 -Action Allow | Out-Null
  Write-Host "Created firewall rule for TCP port 5055." -ForegroundColor Green
}
Write-Host "Now start the app and open http://YOUR-PC-IP:5055 on your phone."
Read-Host "Press Enter to close"
