from pathlib import Path
p=Path(__file__).parent/'wgpu/candidate/wgpu-hal/src/dx12/suballocation.rs'
s=p.read_text()
a=s.index('        match result.and_then(',s.index('    fn finish_placed_resource('));b=s.index('\n    fn sizes(',a)
s=s[:a]+'''        finish_resource_creation(allocation, resource, result, |allocation| {
            self.allocator(pool).lock().free(allocation).map_err(Into::into)
        }).map(|(resource, allocation)| (resource, Allocation::placed(pool, allocation, ty)))
    }
'''+s[b:]
a=s.index('/// Separate general and transient allocators.')
s=s[:a]+'''fn finish_resource_creation<R, A>(
    allocation: A,
    resource: Option<R>,
    result: Result<(), crate::DeviceError>,
    rollback: impl FnOnce(A) -> Result<(), crate::DeviceError>,
) -> Result<(R, A), crate::DeviceError> {
    let error = match (result, resource) {
        (Ok(()), Some(resource)) => return Ok((resource, allocation)),
        (Err(error), resource) => { drop(resource); error },
        (Ok(()), None) => crate::DeviceError::Unexpected,
    };
    rollback(allocation)?;
    Err(error)
}

'''+s[a:]
s+='''

#[cfg(test)]
mod tests {
    use super::finish_resource_creation;
    use core::cell::Cell;

    struct Resource<'a>(&'a Cell<bool>);
    impl Drop for Resource<'_> {
        fn drop(&mut self) { self.0.set(true); }
    }

    #[test]
    fn creation_failure_drops_resource_before_returning_allocation() {
        let dropped = Cell::new(false);
        let rolled_back = Cell::new(false);
        let result = finish_resource_creation(42, Some(Resource(&dropped)), Err(crate::DeviceError::OutOfMemory), |allocation| {
            assert!(dropped.get()); assert_eq!(allocation, 42); rolled_back.set(true); Ok(())
        });
        assert!(matches!(result, Err(crate::DeviceError::OutOfMemory)));
        assert!(rolled_back.get());
    }

    #[test]
    fn null_resource_rolls_back_and_success_keeps_the_allocation() {
        let rolled_back = Cell::new(false);
        let result = finish_resource_creation(42, None::<()>, Ok(()), |_| { rolled_back.set(true); Ok(()) });
        assert!(matches!(result, Err(crate::DeviceError::Unexpected)));
        assert!(rolled_back.get());
        let result = finish_resource_creation(42, Some(17), Ok(()), |_| panic!("success must not roll back"));
        assert!(matches!(result, Ok((17,42))));
    }
}
'''
p.write_text(s)
print('Added resource-creation rollback regression tests without hardware dependency')
