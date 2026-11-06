using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;

internal static class CacheTests
{
    private static object Call(Type launcher, string method, params object[] arguments)
    {
        return launcher.GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, arguments);
    }

    private static void Expect(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    private static int Main(string[] args)
    {
        try
        {
            Type launcher = Assembly.LoadFile(Path.GetFullPath(args[0])).GetType("Launcher", true);
            string root = Path.GetFullPath(args[1]);
            Directory.CreateDirectory(root);
            string first = (string)Call(launcher, "Prepare", root);
            string sample = Path.Combine(first, "_internal", "sample.txt");
            Expect(File.ReadAllText(sample) == "original fixture", "Initial extraction failed");
            DateTime written = File.GetLastWriteTimeUtc(sample);
            Expect((string)Call(launcher, "Prepare", root) == first, "Cache path changed on warm start");
            Expect(File.GetLastWriteTimeUtc(sample) == written, "Warm start rewrote cached files");

            File.WriteAllText(sample, "modified fixture");
            Expect((string)Call(launcher, "Prepare", root) == first, "Repair changed active version path");
            Expect(File.ReadAllText(sample) == "original fixture", "Corruption was not repaired");
            Expect(Directory.GetDirectories(root, "*.invalid-*").Length == 1, "Damaged cache was not isolated");

            File.Delete(sample);
            Call(launcher, "Prepare", root);
            Expect(File.ReadAllText(sample) == "original fixture", "Missing file was not repaired");
            File.WriteAllText(Path.Combine(first, "unexpected.dll"), "not an application resource");
            Call(launcher, "Prepare", root);
            Expect(!File.Exists(Path.Combine(first, "unexpected.dll")), "Unexpected executable was accepted");

            foreach (string path in new string[] { "../outside", "..\\outside", "C:\\outside", "dir/../outside", "name:stream" })
            {
                bool rejected = false;
                try { Call(launcher, "SafePath", root, path); }
                catch (TargetInvocationException) { rejected = true; }
                Expect(rejected, "Unsafe path accepted: " + path);
            }

            string concurrent = Path.Combine(root, "concurrent");
            Directory.CreateDirectory(concurrent);
            Task<string>[] workers = new Task<string>[4];
            for (int i = 0; i < workers.Length; i++)
                workers[i] = Task.Factory.StartNew(() => (string)Call(launcher, "Prepare", concurrent));
            Task.WaitAll(workers);
            foreach (Task<string> worker in workers) Expect(worker.Result == workers[0].Result, "Concurrent cache paths differ");
            Expect(Directory.GetDirectories(concurrent).Length == 1, "Concurrent preparation was not atomic");
            Console.WriteLine("PASS: cold/warm cache, no warm rewrites, corrupt/missing/extra files, unsafe paths and concurrent starts");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
