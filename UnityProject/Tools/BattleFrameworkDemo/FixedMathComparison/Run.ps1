$ErrorActionPreference = 'Stop'
$commit = '743c635dd5b0f6f6bab549c0093382c85f3f8307'
$baseUrl = "https://raw.githubusercontent.com/egametang/ET/$commit/Packages/cn.etetet.truesync/Scripts/Core/Share"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$referenceDir = Join-Path $projectRoot 'Temp/BattleFixedMath-743c635'
$artifactsDir = Join-Path $projectRoot 'Temp/BattleFixedMath-build'
$files = [ordered]@{
    'Fix64.cs' = 'B5EEF5E493DFF85004746544F6B8E685C9581E967912B14F6EE66DF3B7513908'
    'Fix64SinLut.cs' = '3049C49EDE02EA69CB3952E444A7E15373E47C350D55EAEA8E396B6B03126F8F'
    'Fix64TanLut.cs' = '84D9E107BB36E58409CFB6241F530F28352607D0596610C942245CA0BE7A48A6'
    'TSMath.cs' = 'FA07FBB9945738CA59007EBDA1192AC8F76D2EC1AE9342E9B24F175547D3D878'
    'TSMatrix.cs' = 'F763EC485FDA718F51CF95D1DD959F43153E4B6EDC22F8C744A9FFC828F315B8'
    'TSMatrix4x4.cs' = 'C2DAE4ADE9FE6E79E9EC71F9509B7F57770200B8B52AC16F570F3CCF5F2A0CE9'
    'TSQuaternion.cs' = 'AF637E3EE52F6DF5E5B7AA5167BB46C029DB9586DB10C83981C112C12312BEA3'
    'TSVector.cs' = '27EEA12FBC213A0B7B4C47842A77AE3558EB6367DF0643A837949F9740E25DC6'
    'TSVector2.cs' = 'B984A6B8BF0DC52F2399BC89F0436E51ADA79CD25A7BCA021DC5F25E64EC368A'
    'TSVector4.cs' = 'BB9E6A90B32C4F3435F8CBFBC1A26D8F46C6684852F2DADA2EA7ED4C637705FA'
}

New-Item -ItemType Directory -Path $referenceDir -Force | Out-Null
foreach ($name in $files.Keys) {
    $target = Join-Path $referenceDir $name
    if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target).Hash -eq $files[$name]) {
        continue
    }

    curl.exe --fail --silent --show-error --max-time 50 "$baseUrl/$name" -o $target
    if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath $target).Hash -ne $files[$name]) {
        throw "Unable to verify pinned upstream file: $name"
    }
}

dotnet run --project $PSScriptRoot --artifacts-path $artifactsDir
exit $LASTEXITCODE
