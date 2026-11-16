using TEngine;

namespace GameLogic
{
	[Window(UILayer.UI, location : "StartUI", fullScreen: true, hideTimeToClose: 0)]
	public partial class StartUI
	{
		#region 事件

		private partial void OnClick_StartBtn()
		{
			// 开始游戏先留空
			Log.Info("[StartUI] start clicked.");
		}

		private partial void OnClick_QuitBtn()
		{
			Log.Info("[StartUI] quit clicked.");
			
#if UNITY_EDITOR
			
			UnityEditor.EditorApplication.isPlaying = false;
			
#else

			Application.Quit();
			
#endif
		}

		#endregion
	}
}
