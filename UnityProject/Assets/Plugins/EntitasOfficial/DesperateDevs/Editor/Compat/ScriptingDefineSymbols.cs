using System;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build;

namespace DesperateDevs.Unity.Editor
{
    public class ScriptingDefineSymbols
    {
        public static BuildTargetGroup[] BuildTargetGroups
        {
            get
            {
                var enumType = typeof(BuildTargetGroup);
                return Enum.GetNames(enumType)
                    .Where(name => !Attribute.IsDefined(enumType.GetField(name), typeof(ObsoleteAttribute)))
                    .Select(name => (BuildTargetGroup)Enum.Parse(enumType, name))
                    .Where(buildTarget => buildTarget != BuildTargetGroup.Unknown)
                    .ToArray();
            }
        }

        public void Add(string defineSymbol, BuildTargetGroup buildTargetGroup)
        {
            var buildTarget = NamedBuildTarget.FromBuildTargetGroup(buildTargetGroup);
            var symbols = PlayerSettings.GetScriptingDefineSymbols(buildTarget);
            PlayerSettings.SetScriptingDefineSymbols(
                buildTarget,
                Regex.Replace(symbols, $@"\b{defineSymbol}\b", string.Empty) + ";" + defineSymbol
            );
        }

        public void AddForAll(string defineSymbol)
        {
            foreach (var buildTargetGroup in BuildTargetGroups)
                Add(defineSymbol, buildTargetGroup);
        }

        public void Remove(string defineSymbol, BuildTargetGroup buildTargetGroup)
        {
            var buildTarget = NamedBuildTarget.FromBuildTargetGroup(buildTargetGroup);
            var symbols = PlayerSettings.GetScriptingDefineSymbols(buildTarget);
            PlayerSettings.SetScriptingDefineSymbols(
                buildTarget,
                Regex.Replace(symbols, $@"\b{defineSymbol}\b", string.Empty)
            );
        }

        public void RemoveForAll(string defineSymbol)
        {
            foreach (var buildTargetGroup in BuildTargetGroups)
                Remove(defineSymbol, buildTargetGroup);
        }
    }
}
