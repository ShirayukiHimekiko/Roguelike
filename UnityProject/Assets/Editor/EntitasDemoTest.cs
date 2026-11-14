using Entitas;
using UnityEngine;

public static class EntitasDemoTest
{
    public static void Run()
    {
        var contexts = Contexts.sharedInstance;
        contexts.Reset();

        var game = contexts.game;

        var systems = new Systems();
        systems.Add(new DemoMoveSystem(game));
        systems.Initialize();

        var entity = game.CreateEntity();
        entity.AddDemoPosition(0, 0);
        entity.AddDemoVelocity(2, 3);
        entity.isDemoMovable = true;

        systems.Execute();
        systems.Cleanup();

        var ok = entity.demoPosition.X == 2 && entity.demoPosition.Y == 3;
        Debug.Log("ENTITAS_DEMO:" + (ok ? "OK" : "FAIL") + " pos=(" + entity.demoPosition.X + "," + entity.demoPosition.Y + ")");
    }
}
