# Flutter Initialization (Run Locally)

Run these commands in PowerShell:

```powershell
Set-Location 'D:\Codes_Works\Projects\Project9_animation'
flutter create --platforms=android --project-name anime_stream_app --no-pub app
Set-Location 'D:\Codes_Works\Projects\Project9_animation\app'
flutter pub get
flutter run
```

If `flutter pub get` is slow, retry in a stable network environment.
