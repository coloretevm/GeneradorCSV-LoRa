using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Device Manager - TECNIDRO")]
[assembly: AssemblyProduct("Device Manager")]
[assembly: AssemblyCompany("TECNIDRO SRL")]
[assembly: AssemblyCopyright("by Manuel Rodriguez")]
[assembly: AssemblyVersion("1.132.0.0")]
[assembly: AssemblyFileVersion("1.132.0.0")]

internal static class Launcher
{
    private const string Version = "1.132";
    private const string Core = "Device_Manager_Core.exe";
    private static readonly StringComparer Paths = StringComparer.OrdinalIgnoreCase;

    private sealed class Entry
    {
        internal string Name;
        internal string Digest;
        internal long Size;
    }

    private static Stream Resource(string name)
    {
        Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
        if (stream == null) throw new InvalidDataException("Risorsa del programma mancante.");
        return stream;
    }

    private static string Digest(Stream stream)
    {
        using (SHA256 sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    private static string SafePath(string folder, string relative)
    {
        if (String.IsNullOrEmpty(relative) || Path.IsPathRooted(relative) || relative.Contains(":"))
            throw new InvalidDataException("Percorso di risorsa non valido.");
        string[] parts = relative.Replace('/', '\\').Split('\\');
        foreach (string part in parts)
            if (part == "" || part == "." || part == ".." || part.EndsWith(".") || part.EndsWith(" "))
                throw new InvalidDataException("Percorso di risorsa non valido.");
        string root = Path.GetFullPath(folder).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string target = Path.GetFullPath(Path.Combine(folder, relative));
        if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("La risorsa esce dalla cartella cache.");
        return target;
    }

    private static void CheckNotLinked(string path)
    {
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            throw new IOException("La cartella cache non puo contenere collegamenti.");
    }

    private static string CreateRoot()
    {
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (String.IsNullOrEmpty(local)) throw new IOException("Cartella dati utente non disponibile.");
        string root = local;
        foreach (string part in new string[] { "Tecnidro", "DeviceManager", "cache" })
        {
            root = Path.Combine(root, part);
            Directory.CreateDirectory(root);
            CheckNotLinked(root);
        }
        DirectorySecurity security = new DirectorySecurity();
        security.SetAccessRuleProtection(true, false);
        foreach (SecurityIdentifier sid in new SecurityIdentifier[] {
            WindowsIdentity.GetCurrent().User,
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null)
        })
            security.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                PropagationFlags.None, AccessControlType.Allow));
        Directory.SetAccessControl(root, security);
        return root;
    }

    private static Dictionary<string, Entry> ReadManifest(out string cacheId)
    {
        string text;
        using (Stream source = Resource("DM.Manifest"))
        {
            cacheId = Digest(source).Substring(0, 24);
            source.Position = 0;
            using (StreamReader reader = new StreamReader(source, Encoding.UTF8)) text = reader.ReadToEnd();
        }
        Dictionary<string, Entry> entries = new Dictionary<string, Entry>(Paths);
        foreach (string line in text.Split(new char[] { '\n' }, StringSplitOptions.RemoveEmptyEntries))
        {
            string[] fields = line.TrimEnd('\r').Split(new char[] { '\t' }, 3);
            if (fields.Length != 3 || fields[0].Length != 64)
                throw new InvalidDataException("Manifest della cache non valido.");
            string name = fields[2].Replace('/', '\\');
            SafePath(Path.GetTempPath(), name);
            entries.Add(name, new Entry { Name = name, Digest = fields[0],
                Size = Int64.Parse(fields[1], CultureInfo.InvariantCulture) });
        }
        if (!entries.ContainsKey(Core)) throw new InvalidDataException("Applicazione interna mancante.");
        return entries;
    }

    private static bool Verify(string folder, Dictionary<string, Entry> entries)
    {
        if (!Directory.Exists(folder)) return false;
        try
        {
            CheckNotLinked(folder);
            HashSet<string> found = new HashSet<string>(Paths);
            Queue<string> directories = new Queue<string>();
            directories.Enqueue(folder);
            while (directories.Count != 0)
            {
                string directory = directories.Dequeue();
                foreach (string child in Directory.GetDirectories(directory))
                {
                    CheckNotLinked(child);
                    directories.Enqueue(child);
                }
                foreach (string path in Directory.GetFiles(directory))
                {
                    CheckNotLinked(path);
                    string name = path.Substring(folder.Length + 1);
                    Entry expected;
                    if (!entries.TryGetValue(name, out expected) || new FileInfo(path).Length != expected.Size)
                        return false;
                    using (Stream source = File.OpenRead(path))
                        if (Digest(source) != expected.Digest) return false;
                    found.Add(name);
                }
            }
            return found.Count == entries.Count;
        }
        catch (IOException) { return false; }
        catch (UnauthorizedAccessException) { return false; }
    }

    private static void Extract(string stage, Dictionary<string, Entry> entries)
    {
        using (Stream source = Resource("DM.Payload"))
        using (ZipArchive zip = new ZipArchive(source, ZipArchiveMode.Read))
        {
            HashSet<string> found = new HashSet<string>(Paths);
            foreach (ZipArchiveEntry member in zip.Entries)
            {
                string name = member.FullName.Replace('/', '\\');
                Entry expected;
                if (!entries.TryGetValue(name, out expected) || !found.Add(name) || member.Length != expected.Size)
                    throw new InvalidDataException("Contenuto della cache non valido.");
                string target = SafePath(stage, name);
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                using (Stream input = member.Open())
                using (FileStream output = new FileStream(target, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                    input.CopyTo(output);
            }
            if (found.Count != entries.Count || !Verify(stage, entries))
                throw new InvalidDataException("Verifica dei file del programma non riuscita.");
        }
    }

    private static string Prepare(string root)
    {
        string cacheId;
        Dictionary<string, Entry> entries = ReadManifest(out cacheId);
        string name = "v" + Version + "-" + cacheId;
        string folder = SafePath(root, name);
        using (Mutex gate = new Mutex(false, "Local\\Tecnidro.DeviceManager." + cacheId))
        {
            bool acquired = false;
            try
            {
                try { acquired = gate.WaitOne(TimeSpan.FromMinutes(5)); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired) throw new IOException("Un altro avvio sta preparando il programma. Riprova tra poco.");
                if (!Verify(folder, entries))
                {
                    string stage = SafePath(root, "preparing-" + Guid.NewGuid().ToString("N"));
                    Directory.CreateDirectory(stage);
                    Extract(stage, entries);
                    if (Directory.Exists(folder))
                    {
                        CheckNotLinked(folder);
                        string previous = SafePath(root, name + ".invalid-" + Guid.NewGuid().ToString("N"));
                        Directory.Move(folder, previous);
                    }
                    Directory.Move(stage, folder);
                }
            }
            finally { if (acquired) gate.ReleaseMutex(); }
        }
        return folder;
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string original = Path.GetFullPath(Assembly.GetExecutingAssembly().Location);
            string cache = Prepare(CreateRoot());
            ProcessStartInfo start = new ProcessStartInfo(SafePath(cache, Core));
            start.WorkingDirectory = Path.GetDirectoryName(original);
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.EnvironmentVariables["DEVICE_MANAGER_PORTABLE_EXE"] = original;
            start.EnvironmentVariables["DEVICE_MANAGER_PORTABLE_PID"] = Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture);
            if (args.Length == 1 && args[0] == "--startup-probe") start.Arguments = "--startup-probe";
            using (Process child = Process.Start(start))
            {
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show("Impossibile avviare Device Manager.\n\n" + error.Message,
                "Device Manager - TECNIDRO", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
