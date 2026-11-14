using Entitas;
using UnityEngine;

public sealed class EntitasDemoBehaviour : MonoBehaviour
{
    EntitasDemoSystems _systems;
    GameContext _game;

    public Feature Systems => _systems;

    void Start()
    {
        _game = Contexts.sharedInstance.game;

        _systems = new EntitasDemoSystems(_game);
        _systems.Initialize();

        var entity = _game.CreateEntity();
        entity.AddDemoPosition(0, 0);
        entity.AddDemoVelocity(1, 0);
        entity.isDemoMovable = true;

        Debug.Log("ENTITAS_DEMO_BEHAVIOUR:READY entityIndex=" + entity.creationIndex);
    }

    void Update()
    {
        _systems.Execute();
        _systems.Cleanup();
    }

    void OnGUI()
    {
        var group = _game.GetGroup(GameMatcher.DemoPosition);
        var entities = group.GetEntities();

        GUI.Label(new Rect(10, 10, 420, 24), "Entitas entities: " + entities.Length);

        for (var i = 0; i < entities.Length; i++)
        {
            var entity = entities[i];
            GUI.Label(new Rect(10, 34 + i * 22, 420, 24),
                "entity[" + entity.creationIndex + "] pos=(" + entity.demoPosition.X + "," + entity.demoPosition.Y + ")");
        }
    }

    void OnDestroy()
    {
        _systems.TearDown();

#if UNITY_EDITOR
        if (_systems.gameObject != null)
        {
            Destroy(_systems.gameObject);
        }
#endif

        Contexts.sharedInstance.Reset();
    }
}
