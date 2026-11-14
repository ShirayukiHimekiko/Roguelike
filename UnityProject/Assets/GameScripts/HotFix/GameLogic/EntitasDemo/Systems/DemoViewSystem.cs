using System.Collections.Generic;
using Entitas;
using Entitas.Unity;
using UnityEngine;

public sealed class DemoViewSystem : IExecuteSystem, ITearDownSystem
{
    readonly IGroup<GameEntity> _positions;
    readonly Dictionary<int, GameObject> _views = new Dictionary<int, GameObject>();

    public DemoViewSystem(GameContext context)
    {
        _positions = context.GetGroup(GameMatcher.DemoPosition);
    }

    public void Execute()
    {
        var entities = _positions.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            var entity = entities[i];

            if (!_views.TryGetValue(entity.creationIndex, out var view) || view == null)
            {
                view = GameObject.CreatePrimitive(PrimitiveType.Cube);
                view.name = "DemoEntity_" + entity.creationIndex;
                view.transform.localScale = Vector3.one * 0.5f;
                view.Link(entity);
                _views[entity.creationIndex] = view;
            }

            view.transform.position = new Vector3(entity.demoPosition.X, entity.demoPosition.Y, 0f);
        }
    }

    public void TearDown()
    {
        foreach (var view in _views.Values)
        {
            if (view == null)
            {
                continue;
            }

            view.Unlink();
            Object.Destroy(view);
        }

        _views.Clear();
    }
}
