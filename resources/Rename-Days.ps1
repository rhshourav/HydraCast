# Clear the screen for a clean prompt
Clear-Host

# 1. Prompt for the target folder
$targetDir = Read-Host "Enter the full path of the folder"
$targetDir = $targetDir.Trim('"').Trim("'")

if (-Not (Test-Path -Path $targetDir -PathType Container)) {
    Write-Host "Error: The specified folder does not exist." -ForegroundColor Red
    Pause
    exit
}

# 2. Prompt for the naming direction (Option for short or long names)
Write-Host "`nSelect Renaming Option:" -ForegroundColor Cyan
Write-Host "1. Short to Long (e.g., _MON_ to _MONDAY_)"
Write-Host "2. Long to Short (e.g., _MONDAY_ to _MON_)"
$choice = Read-Host "Enter 1 or 2"

if ($choice -ne '1' -and $choice -ne '2') {
    Write-Host "Invalid choice. Exiting..." -ForegroundColor Red
    Pause
    exit
}

# 3. Define the day mappings
$days = @(
    [pscustomobject]@{Short="MON"; Long="MONDAY"},
    [pscustomobject]@{Short="TUE"; Long="TUESDAY"},
    [pscustomobject]@{Short="WED"; Long="WEDNESDAY"},
    [pscustomobject]@{Short="THU"; Long="THURSDAY"},
    [pscustomobject]@{Short="FRI"; Long="FRIDAY"},
    [pscustomobject]@{Short="SAT"; Long="SATURDAY"},
    [pscustomobject]@{Short="SUN"; Long="SUNDAY"}
)

Write-Host "`nProcessing files and folders in: $targetDir" -ForegroundColor Yellow
Write-Host "--------------------------------------------------"

# Helper function to process renaming
function Rename-Items {
    param($items, $oldStr, $newStr)
    foreach ($item in $items) {
        # Using regex escape to safely replace text ignoring case
        $newName = $item.Name -ireplace [regex]::Escape($oldStr), $newStr
        if ($item.Name -cne $newName) {
            Write-Host "Renaming: $($item.Name)  ->  $newName" -ForegroundColor Green
            Rename-Item -Path $item.FullName -NewName $newName -ErrorAction SilentlyContinue
        }
    }
}

# 4. Loop through the days and perform the rename
foreach ($day in $days) {
    # Set the search and replace strings based on the user's choice
    if ($choice -eq '1') {
        $search = "_$($day.Short)_"
        $replace = "_$($day.Long)_"
    } else {
        $search = "_$($day.Long)_"
        $replace = "_$($day.Short)_"
    }

    # Step A: Rename Files
    $files = Get-ChildItem -Path $targetDir -Recurse -File | Where-Object { $_.Name -match [regex]::Escape($search) }
    if ($files) { Rename-Items -items $files -oldStr $search -newStr $replace }

    # Step B: Rename Folders
    # We sort by length descending to rename the deepest subfolders first
    $folders = Get-ChildItem -Path $targetDir -Recurse -Directory | Where-Object { $_.Name -match [regex]::Escape($search) } | Sort-Object -Property @{Expression={$_.FullName.Length}; Descending=$true}
    if ($folders) { Rename-Items -items $folders -oldStr $search -newStr $replace }
}

Write-Host "--------------------------------------------------"
Write-Host "Done! All matching days have been updated." -ForegroundColor Cyan
Pause
