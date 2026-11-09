using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

internal static class DeviceIdentity
{
    private static string Hex(byte[] bytes) { return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant(); }
    private static string Base64(byte[] bytes) { return Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_'); }
    private static string Hash(string value) { using (SHA256 sha = SHA256.Create()) return Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(value))); }
    private static void NotLinked(string path)
    {
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("Identity storage cannot be a link.");
    }
    public static int Main()
    {
        try
        {
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            string input = Console.In.ReadToEnd();
            if (input.Length > 65536) throw new InvalidDataException("Request too large.");
            Dictionary<string, object> request = serializer.Deserialize<Dictionary<string, object>>(input);
            string origin = (string)request["origin"];
            Uri uri;
            if (!Uri.TryCreate(origin, UriKind.Absolute, out uri) || uri.Scheme != "https" || uri.AbsolutePath != "/"
                || uri.Query != "" || uri.Fragment != "" || uri.UserInfo != "" || origin != uri.GetLeftPart(UriPartial.Authority))
                throw new InvalidDataException("Invalid service origin.");
            string operation = (string)request["operation"];
            if (operation != "identity" && operation != "sign") throw new InvalidDataException("Unknown operation.");
            string folder = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            foreach (string part in new string[] { "Tecnidro", "DeviceManager", "identities" })
            {
                folder = Path.Combine(folder, part);
                Directory.CreateDirectory(folder);
                NotLinked(folder);
            }
            string id = Hash(origin);
            string path = Path.Combine(folder, id + ".bin");
            byte[] entropy = Encoding.UTF8.GetBytes(origin);
            using (Mutex gate = new Mutex(false, "Local\\Tecnidro.Identity." + id))
            {
                bool locked = false;
                try
                {
                    try { locked = gate.WaitOne(TimeSpan.FromSeconds(30)); }
                    catch (AbandonedMutexException) { locked = true; }
                    if (!locked) throw new IOException("Another process is preparing the device identity.");
                    using (RSACryptoServiceProvider rsa = new RSACryptoServiceProvider(2048, new CspParameters(24)))
                    {
                        rsa.PersistKeyInCsp = false;
                        if (File.Exists(path))
                        {
                            NotLinked(path);
                            byte[] plain = ProtectedData.Unprotect(File.ReadAllBytes(path), entropy, DataProtectionScope.CurrentUser);
                            try { rsa.ImportCspBlob(plain); }
                            finally { Array.Clear(plain, 0, plain.Length); }
                        }
                        else
                        {
                            byte[] plain = rsa.ExportCspBlob(true);
                            byte[] encrypted;
                            try { encrypted = ProtectedData.Protect(plain, entropy, DataProtectionScope.CurrentUser); }
                            finally { Array.Clear(plain, 0, plain.Length); }
                            string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
                            using (FileStream stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                            { stream.Write(encrypted, 0, encrypted.Length); stream.Flush(true); }
                            File.Move(temporary, path);
                        }
                        RSAParameters parameters = rsa.ExportParameters(false);
                        string modulus = Base64(parameters.Modulus);
                        string exponent = Base64(parameters.Exponent);
                        Dictionary<string, object> result = new Dictionary<string, object>();
                        result["id"] = Hash(modulus + "." + exponent);
                        result["jwk"] = new Dictionary<string, string> { { "kty", "RSA" }, { "n", modulus }, { "e", exponent } };
                        if (operation == "sign")
                        {
                            byte[] message = Encoding.UTF8.GetBytes((string)request["message"]);
                            result["signature"] = Base64(rsa.SignData(message, "SHA256"));
                        }
                        Console.Out.Write(serializer.Serialize(result));
                        return 0;
                    }
                }
                finally { if (locked) gate.ReleaseMutex(); }
            }
        }
        catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
    }
}
