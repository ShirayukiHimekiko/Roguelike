using Cysharp.Threading.Tasks;
using TEngine;
using UnityEngine;
using UnityEngine.InputSystem;

namespace GameLogic
{
	[Window(UILayer.UI, location : "StartUI", fullScreen: true, hideTimeToClose: 0)]
	public partial class StartUI
	{
		#region 事件

		private partial void OnClick_StartBtn()
		{
			BattleManager.Instance.StartBattle();
		}

		/// <summary>
		/// 读取菜单中的上一局回放快捷键。
		/// </summary>
		protected override void OnUpdate()
		{
			Keyboard keyboard = Keyboard.current;
			if (keyboard != null && keyboard.rKey.wasPressedThisFrame)
			{
				BattleManager.Instance.StartLastReplayAsync().Forget();
			}
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
