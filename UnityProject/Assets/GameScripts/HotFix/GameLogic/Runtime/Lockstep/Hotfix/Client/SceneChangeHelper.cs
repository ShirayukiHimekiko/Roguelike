using UnityEngine.SceneManagement;

namespace GameLogic
{
    /// <summary>当局绑定的本地场景是否已就绪。</summary>
    internal enum LocalSceneReadiness
    {
        Waiting,
        Ready,
        Unavailable
    }

    /// <summary>实时局与回放局共用的本地场景绑定。当前模式复用宿主已打开的场景。</summary>
    internal static class SceneChangeHelper
    {
        /// <summary>绑定发起进场的场景实例，避免稍后在另一场景误启动旧房间。</summary>
        internal static Scene BindActiveScene()
        {
            return SceneManager.GetActiveScene();
        }

        /// <summary>确定当前房间能否继续等待或开始演算。</summary>
        internal static LocalSceneReadiness GetReadiness(Scene scene)
        {
            if (!scene.IsValid() || SceneManager.GetActiveScene().handle != scene.handle)
            {
                return LocalSceneReadiness.Unavailable;
            }

            return scene.isLoaded ? LocalSceneReadiness.Ready : LocalSceneReadiness.Waiting;
        }
    }
}
